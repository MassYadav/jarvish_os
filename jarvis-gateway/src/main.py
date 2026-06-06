import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
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

app = FastAPI(title="JARVIS API Gateway", lifespan=lifespan)

app.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(intent.router, prefix="/v1/intent", tags=["Intent"])
app.include_router(voice.router, prefix="/v1/stream/voice", tags=["Voice"])

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "optimal"}