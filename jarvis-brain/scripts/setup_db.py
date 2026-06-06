from sqlalchemy import create_engine, text
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)

def setup():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            task_id UUID PRIMARY KEY,
            user_id UUID,
            intent TEXT,
            status VARCHAR(50),
            result_payload TEXT
        );
        """))
        conn.commit()
    print("Agent Tasks table created successfully.")

if __name__ == "__main__":
    setup()