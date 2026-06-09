from typing import Dict, Any
from uuid import UUID
from sqlalchemy import create_engine, text
from src.core.config import settings
from src.memory.base import BaseMemoryProvider
from src.core.logger import logger

engine = create_engine(settings.DATABASE_URL)

class PostgresMemoryAdapter(BaseMemoryProvider):
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        try:
            # If user_id is not a UUID, return default context instead of crashing
            try:
                UUID(user_id)
            except (ValueError, AttributeError):
                logger.warning(f"Invalid UUID format: {user_id}. Using default context.")
                return {"preferences": {}}

            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT preferences FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()
                return result[0] if result and result[0] else {"preferences": {}}
        except Exception as e:
            logger.warning(f"Memory lookup failed for {user_id}: {e}")
            return {"preferences": {}}