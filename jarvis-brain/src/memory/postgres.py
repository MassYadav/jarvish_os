from typing import Dict, Any
from sqlalchemy import create_engine, text
from src.core.config import settings
from src.memory.base import BaseMemoryProvider
from src.core.logger import logger

engine = create_engine(settings.DATABASE_URL)

class PostgresMemoryAdapter(BaseMemoryProvider):
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT preferences FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()
                return result[0] if result and result[0] else {}
        except Exception as e:
            logger.error("postgres_memory_failed", error=str(e))
            return {}