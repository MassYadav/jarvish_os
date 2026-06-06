import asyncio
from src.db.session import engine
from src.db.models import Base
import structlog

logger = structlog.get_logger()

async def init_models():
    logger.info("building_database_schemas")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) # Clean slate for MVP
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schemas_ready")

if __name__ == "__main__":
    asyncio.run(init_models())