import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.db.session import engine
from src.api.v1 import intent, voice, auth, keys

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Strictly connection pools. No schema creation here to prevent K8s race conditions.
    logger.info("initializing_async_connection_pools")
    yield
    logger.info("disposing_connection_pools")
    await engine.dispose()

app = FastAPI(title="JARVIS OS Gateway", lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(intent.router, prefix="/v1/intent", tags=["Intent"])
app.include_router(voice.router, prefix="/v1/stream/voice", tags=["Voice"])
app.include_router(keys.router, prefix="/v1/keys", tags=["Keys"])

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "optimal"}


# --- PHASE 5 INTEGRATION: UI to Worker Bridge ---
from pydantic import BaseModel, UUID4
from typing import Optional
import uuid
import json
from redis import Redis
from sqlalchemy import create_engine, text
from src.core.config import settings

# Import our new AES-256-GCM Vault
from src.core.security import vault

# Connect to databases (Replacing asyncpg with psycopg2 for sync stability here)
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(sync_db_url)
sync_redis = Redis.from_url(settings.REDIS_URL)


class ExecutionConfig(BaseModel):
    """Runtime LLM configuration submitted by the UI with every task."""
    active_provider: str  # e.g. "groq", "gemini", "ollama"
    active_model: str     # e.g. "llama-3.1-70b-versatile", "gemini-1.5-flash"
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None


class TaskRequest(BaseModel):
    """Full task submission payload from the Next.js frontend."""
    message: str          # The natural language command
    user_id: UUID4        # Strict UUID — no plain strings accepted
    config: ExecutionConfig

@app.post("/tasks")
def create_task(req: TaskRequest):
    task_id = str(uuid.uuid4())
    # UUID4 validation is done by Pydantic — safe to cast directly
    user_id_str = str(req.user_id)
    decrypted_vault_keys: dict = {}

    with sync_engine.connect() as conn:
        # 0. Check for Universal Clarification Engine resumption
        row = conn.execute(
            text("""
                SELECT task_id 
                FROM agent_tasks 
                WHERE status = 'WAITING_FOR_USER' 
                LIMIT 1
            """)
            # Note: We should filter by user_id, but the schema doesn't have it natively mapped in this version.
            # Using the first WAITING_FOR_USER task found for now since it's a single-user system typically.
        ).fetchone()

        if row:
            resume_task_id = row[0]
            logger.info("resuming_suspended_task", task_id=resume_task_id)
            
            # Update DB to RUNNING to prevent double-resumes
            conn.execute(
                text("""
                    UPDATE agent_tasks 
                    SET status = 'RUNNING' 
                    WHERE task_id = :tid
                """),
                {"tid": resume_task_id}
            )
            conn.commit()

            # Push resumption payload to Brain
            resume_data = {
                "task_id": resume_task_id,
                "user_id": user_id_str,
                "intent": None,  # Brain handles intent = None as a resume operation
                "user_clarification_response": req.message,
                "api_keys": {}
            }
            sync_redis.rpush("jarvis_execution_queue", json.dumps(resume_data))
            
            return {"task_id": resume_task_id, "status": "RESUMING", "message": "Resumed from clarification"}

        # 1. Register the new task for UI polling
        conn.execute(
            text("""
                INSERT INTO agent_tasks (task_id, status)
                VALUES (:tid, 'QUEUED')
                ON CONFLICT DO NOTHING
            """),
            {"tid": task_id},
        )

        # 2. Attempt to supplement inline keys with any vault-stored credentials
        try:
            rows = conn.execute(
                text("""
                    SELECT service_name, ciphertext, nonce
                    FROM vault_credentials
                    WHERE user_id = :uid
                """),
                {"uid": user_id_str},
            ).fetchall()

            for row in rows:
                service_name, ciphertext, nonce = row[0], row[1], row[2]
                try:
                    plain_key = vault._decrypt_sync(
                        ciphertext, nonce, user_id_str, service_name
                    )
                    decrypted_vault_keys[f"{service_name}_key"] = plain_key
                    logger.info(
                        "vault_key_decrypted",
                        user_id=user_id_str,
                        provider=service_name,
                    )
                except Exception as e:
                    logger.error(
                        "vault_decryption_failed",
                        provider=service_name,
                        error=str(e),
                    )
        except Exception as db_e:
            logger.error("vault_db_query_failed", error=str(db_e))

        conn.commit()

    # 3. Build the merged api_keys dict.
    #    Priority: vault-decrypted > inline from ExecutionConfig
    #    The Brain's LLM factory reads keys as "{provider}_key" entries.
    config = req.config
    inline_keys: dict = {
        k: v
        for k, v in {
            "groq_key": config.groq_api_key,
            "gemini_key": config.gemini_api_key,
            "openai_key": config.openai_api_key,
            "anthropic_key": config.anthropic_api_key,
            "openrouter_key": config.openrouter_api_key,
            "preferred_provider": config.active_provider,
        }.items()
        if v  # strip None / empty string values
    }
    # Vault keys win — they are encrypted and verified
    final_api_keys = {**inline_keys, **decrypted_vault_keys}

    # 4. Push full payload onto the Redis queue for the Brain worker
    task_data = {
        "task_id": task_id,
        "user_id": user_id_str,
        "intent": req.message,          # frontend sends "message", brain calls it "intent"
        "api_keys": final_api_keys,
        "execution_config": {
            "active_provider": config.active_provider,
            "active_model": config.active_model,
        },
    }
    sync_redis.rpush("jarvis_execution_queue", json.dumps(task_data))

    logger.info("task_queued", task_id=task_id, provider=config.active_provider, model=config.active_model)
    return {"task_id": task_id, "status": "QUEUED"}

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    from fastapi import HTTPException
    with sync_engine.connect() as conn:
        row = conn.execute(text("""
            SELECT status, risk_score, result_payload 
            FROM agent_tasks 
            WHERE task_id = :tid
        """), {"tid": task_id}).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
            
        return {
            "status": row[0],
            "risk_score": row[1] if row[1] is not None else 0,
            "result_payload": row[2] if row[2] is not None else ""
        }

@app.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str):
    with sync_engine.connect() as conn:
        conn.execute(text("""
            UPDATE agent_tasks 
            SET status = 'QUEUED'
            WHERE task_id = :tid
        """), {"tid": task_id})
        conn.commit()

    # Sending 'None' triggers a LangGraph thread resume. The Brain already has the keys in its state memory.
    payload = json.dumps({
        "task_id": task_id,
        "user_id": "user_123", # Dummy ID used just to bypass validation on resume
        "intent": None, 
        "api_keys": {}
    })
    sync_redis.rpush("jarvis_execution_queue", payload)

    return {"status": "approved"}

@app.post("/tasks/{task_id}/deny")
def deny_task(task_id: str):
    from fastapi import HTTPException
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("""
                UPDATE agent_tasks 
                SET status = 'FAILED'
                WHERE task_id = :tid
            """), {"tid": task_id})
            conn.commit()
        
        logger.info("task_denied", task_id=task_id)
        return {"task_id": task_id, "status": "FAILED", "message": "Task denied by human"}
    except Exception as e:
        logger.error("task_denial_failed", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Denial failed: {str(e)}")