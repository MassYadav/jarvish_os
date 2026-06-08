import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.db.session import engine
from src.api.v1 import intent, voice, auth

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

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "optimal"}


# --- PHASE 5 INTEGRATION: UI to Worker Bridge ---
from pydantic import BaseModel
import uuid
import json
from redis import Redis
from sqlalchemy import create_engine, text
from src.core.config import settings

# 1. Connect to our databases (Replacing asyncpg with psycopg2 for sync stability here)
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(sync_db_url)
sync_redis = Redis.from_url(settings.REDIS_URL)

class TaskPayload(BaseModel):
    intent: str
    user_id: str
    api_keys: dict = {}

@app.post("/tasks")
def create_task(payload: TaskPayload):
    # Generate the UUID tracking number
    task_id = str(uuid.uuid4())
    
    # Push the command to the Redis Queue for the JARVIS Worker to catch
    task_data = {
        "task_id": task_id,
        "user_id": payload.user_id,
        "intent": payload.intent,
        "api_keys": payload.api_keys
    }
    sync_redis.rpush("jarvis_execution_queue", json.dumps(task_data))
    
    # Insert a placeholder row into PostgreSQL so the UI has something to poll
    with sync_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agent_tasks (task_id, status) 
            VALUES (:tid, 'QUEUED') 
            ON CONFLICT DO NOTHING
        """), {"tid": task_id})
        conn.commit()
        
    return {"task_id": task_id, "status": "QUEUED"}

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    # The UI polls this endpoint every 2 seconds to get updates from the worker
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