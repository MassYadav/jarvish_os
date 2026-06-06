import uuid
import json
from redis import Redis

redis_conn = Redis(host="localhost", port=6380, db=0)

task_id = str(uuid.uuid4())
user_id = str(uuid.uuid4())

# Notice we provide a BAD Groq key to force the failover to Ollama!
payload = {
    "task_id": task_id,
    "user_id": user_id,
    "intent": "Verify BYOAK Failover Architecture.",
    "api_keys": {
        "groq": "gsk_fake_key_to_force_failure",
        "gemini": ""
    }
}

print(f"Pushing Task {task_id} to Queue...")
redis_conn.rpush("jarvis_execution_queue", json.dumps(payload))
print("Done. Check your worker terminal!")