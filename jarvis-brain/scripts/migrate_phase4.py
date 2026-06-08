from sqlalchemy import create_engine, text
from src.core.config import settings
from src.core.logger import logger

engine = create_engine(settings.DATABASE_URL)

def run_migration():
    logger.info("starting_phase_4_db_migration")
    with engine.connect() as conn:
        # We use IF NOT EXISTS/safe alters to prevent crashing if run twice
        queries = [
            "ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS step_results JSONB DEFAULT '{}'::jsonb;",
            "ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS risk_score INTEGER DEFAULT 0;",
            "ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS requires_hitl BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS execution_plan JSONB;"
        ]
        
        for query in queries:
            try:
                conn.execute(text(query))
            except Exception as e:
                # Ignore duplicate column errors in Postgres
                if "already exists" not in str(e):
                    logger.error("migration_error", error=str(e))
        
        conn.commit()
    logger.info("migration_complete")

if __name__ == "__main__":
    run_migration()