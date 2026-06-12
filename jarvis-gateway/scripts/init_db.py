import asyncio
from sqlalchemy import text
from src.db.session import engine
from src.db.models import Base
import structlog

logger = structlog.get_logger()

async def init_models():
    logger.info("building_database_schemas")
    async with engine.begin() as conn:
        # Clean slate for MVP
        await conn.run_sync(Base.metadata.drop_all) 
        await conn.run_sync(Base.metadata.create_all)
        
        # --- NEW: Seed the Temporary Development User ---
        logger.info("seeding_development_user")
        TEMP_DEV_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
        
        # We must await the execution in async SQLAlchemy
        await conn.execute(text("""
            INSERT INTO users (id, email) 
            VALUES (:uid, 'admin@jarvis.local') 
            ON CONFLICT (id) DO NOTHING
        """), {"uid": TEMP_DEV_USER_ID})
        
        # Fallback to handle unique constraint on email just in case
        await conn.execute(text("""
            INSERT INTO users (id, email) 
            VALUES (:uid, 'admin@jarvis.local') 
            ON CONFLICT (email) DO NOTHING
        """), {"uid": TEMP_DEV_USER_ID})

    logger.info("database_schemas_ready")

if __name__ == "__main__":
    asyncio.run(init_models())