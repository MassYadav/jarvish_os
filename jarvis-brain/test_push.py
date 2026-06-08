import json
import uuid
from redis import Redis
from src.core.config import settings

redis_conn = Redis.from_url(settings.REDIS_URL)

generated_task_id = str(uuid.uuid4())
generated_user_id = str(uuid.uuid4())

test_payload = {
    "task_id": generated_task_id,
    "user_id": generated_user_id,
    # Low-risk read intent that should bypass HITL restrictions
    "intent": "List all the files and folders in the current directory.",
    "api_keys": {
        "groq": "",   
        "gemini": ""
    }
}

print(f"Connecting to Redis at: {settings.REDIS_URL}")
redis_conn.rpush("jarvis_execution_queue", json.dumps(test_payload))
print("🚀 Low-risk Integration Test Payload pushed!")