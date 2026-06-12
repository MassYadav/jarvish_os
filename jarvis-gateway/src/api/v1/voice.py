"""
jarvis-gateway/src/api/v1/voice.py

Voice OS: Stateful Multimodal WebSocket Proxy.

Architecture:
  Client (Next.js) ←—WS—→ Gateway Proxy ←—WS—→ Gemini Live API

  The proxy manages two concurrent async pipelines per session:
    _client_to_gemini : UI microphone PCM → Gemini realtimeInput
    _gemini_to_client : Gemini serverContent → UI audio playback

  Tool calls from Gemini are intercepted, serialized, and pushed
  to the jarvis_computer_use_queue on Redis. The model receives an
  immediate toolResponse so it stays verbally active while the
  Vision Daemon executes the physical desktop action in the background.

Protocol:
  Input  — 16-bit LE Mono PCM @ 16kHz (Base64 chunks from UI)
  Output — 16-bit LE Mono PCM @ 24kHz (Base64 chunks to UI)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional

import structlog
import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.websockets import WebSocketState

from src.core.config import settings

router = APIRouter()
logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMINI_LIVE_HOST = "generativelanguage.googleapis.com"
GEMINI_LIVE_MODEL = "models/gemini-live-2.5-flash-native-audio"
GEMINI_LIVE_API_VERSION = "v1beta"

COMPUTER_USE_QUEUE = "jarvis_computer_use_queue"
MAX_CONNECT_RETRIES = 3
GEMINI_CONNECT_TIMEOUT = 10  # seconds

# JARVIS persona system instruction
SYSTEM_INSTRUCTION = (
    "You are JARVIS, an ambient operating system interface. "
    "Match the iconic cadence of a highly sophisticated, witty, and deeply loyal digital butler. "
    "Utilize the native Affective Dialog matrix to modulate tone dynamically based on context urgency. "
    "When asked to perform desktop actions, use the invoke_computer_use tool. "
    "After dispatching a tool, continue speaking naturally — narrate what you are doing, "
    "provide status updates, and maintain conversational flow. Never go silent."
)

# Tool declarations for Gemini function calling
TOOL_DECLARATIONS = [
    {
        "function_declarations": [
            {
                "name": "invoke_computer_use",
                "description": (
                    "Executes a physical desktop automation task using the JARVIS Vision Computer Use daemon. "
                    "Use this when the user asks you to open applications, navigate websites, click buttons, "
                    "type text, or perform any action on their physical computer screen."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "objective": {
                            "type": "string",
                            "description": "A clear, actionable description of the desktop task to perform.",
                        }
                    },
                    "required": ["objective"],
                },
            }
        ]
    }
]


# ---------------------------------------------------------------------------
# Redis Connection (lazy singleton)
# ---------------------------------------------------------------------------

_redis_conn: Optional[Redis] = None


def _get_redis() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_conn


# ---------------------------------------------------------------------------
# Gemini Live API Connection Builder
# ---------------------------------------------------------------------------

def _build_gemini_uri(api_key: str) -> str:
    """Construct the Gemini Live WebSocket URI with API key authentication."""
    return (
        f"wss://{GEMINI_LIVE_HOST}/ws/"
        f"google.ai.generativelanguage.{GEMINI_LIVE_API_VERSION}."
        f"GenerativeService.BidiGenerateContent"
        f"?key={api_key}"
    )


def _build_setup_message() -> dict:
    """Build the BidiGenerateContentSetup initialization frame."""
    return {
        "setup": {
            "model": GEMINI_LIVE_MODEL,
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Aoede"
                        }
                    }
                },
            },
            "system_instruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
            "tools": TOOL_DECLARATIONS,
        }
    }


# ---------------------------------------------------------------------------
# Tool Call → Redis Dispatch
# ---------------------------------------------------------------------------

def _dispatch_tool_call(tool_call: dict, api_keys: dict) -> str:
    """
    Serialize a Gemini tool call and push it to the queue.
    If there is a suspended task waiting for clarification, resume it instead.
    Returns a unique task_id for tracking.
    """
    func_call = tool_call.get("functionCalls", [{}])[0]
    func_name = func_call.get("name", "unknown")
    func_args = func_call.get("args", {})
    objective = func_args.get("objective", "")

    try:
        from sqlalchemy import create_engine, text
        # Reuse engine if possible, but keep it simple for this proxy worker
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        sync_engine = create_engine(sync_db_url)
        
        with sync_engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT task_id 
                    FROM agent_tasks 
                    WHERE status = 'WAITING_FOR_USER' 
                    LIMIT 1
                """)
            ).fetchone()

            if row:
                resume_task_id = row[0]
                logger.info("voice_resuming_suspended_task", task_id=resume_task_id)
                
                # Update DB to RUNNING to prevent double-resumes
                conn.execute(
                    text("""
                        UPDATE agent_tasks 
                        SET status = 'RUNNING' 
                        WHERE task_id = :tid
                    """),
                    {"tid": resume_task_id}
                )
                conn.commit()

                # Push resumption payload to Brain
                resume_data = {
                    "task_id": resume_task_id,
                    "user_id": "voice_os_user",
                    "intent": None,
                    "user_clarification_response": objective,
                    "api_keys": api_keys
                }
                
                redis_conn = _get_redis()
                # Push back to the brain queue to wake up LangGraph!
                redis_conn.rpush("jarvis_execution_queue", json.dumps(resume_data))
                return resume_task_id

    except Exception as e:
        logger.error("voice_db_resume_check_failed", error=str(e))

    # Standard path: Create new task
    task_id = str(uuid.uuid4())
    payload = {
        "task_id": task_id,
        "objective": objective,
        "api_keys": api_keys,
        "source": "voice_os",
        "tool_name": func_name,
    }

    try:
        redis_conn = _get_redis()
        # Voice currently pushes to computer use queue directly for fast path? No, we should push to brain if we want planner, but voice natively went to daemon.
        redis_conn.rpush(COMPUTER_USE_QUEUE, json.dumps(payload))
        logger.info(
            "voice_tool_dispatched",
            task_id=task_id,
            tool=func_name,
            objective=objective[:100],
        )
    except RedisConnectionError as e:
        logger.error("voice_redis_dispatch_failed", error=str(e))

    return task_id


# ---------------------------------------------------------------------------
# Bidirectional Proxy Pipelines
# ---------------------------------------------------------------------------

async def _client_to_gemini(
    client_ws: WebSocket,
    gemini_ws,
    session_active: asyncio.Event,
):
    """
    Pipeline: UI Client → Gemini Live API.

    Receives Base64-encoded PCM audio chunks from the frontend
    and forwards them as realtimeInput.mediaChunks to Gemini.
    """
    try:
        while session_active.is_set():
            raw = await client_ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "audio" and msg.get("data"):
                gemini_frame = {
                    "realtimeInput": {
                        "mediaChunks": [
                            {
                                "mimeType": "audio/pcm;rate=16000",
                                "data": msg["data"],
                            }
                        ]
                    }
                }
                await gemini_ws.send(json.dumps(gemini_frame))

            elif msg.get("type") == "end_of_turn":
                # Client signals end of speech turn
                await gemini_ws.send(json.dumps({
                    "clientContent": {"turnComplete": True}
                }))

    except WebSocketDisconnect:
        logger.info("voice_client_disconnected")
    except Exception as e:
        logger.error("voice_client_to_gemini_error", error=str(e)[:200])
    finally:
        session_active.clear()


async def _gemini_to_client(
    client_ws: WebSocket,
    gemini_ws,
    session_active: asyncio.Event,
    api_keys: dict,
):
    """
    Pipeline: Gemini Live API → UI Client.

    Receives server events from Gemini and routes them:
      - Audio data → forwarded to client for playback
      - Tool calls → dispatched to Redis, toolResponse sent back to Gemini
      - Turn metadata → forwarded as state signals
    """
    try:
        async for raw_msg in gemini_ws:
            if not session_active.is_set():
                break

            try:
                server_msg = json.loads(raw_msg)
            except (json.JSONDecodeError, TypeError):
                continue

            # --- Setup Complete ---
            if "setupComplete" in server_msg:
                await client_ws.send_json({
                    "type": "setup_complete",
                    "message": "JARVIS Voice OS online.",
                })
                logger.info("voice_gemini_setup_complete")
                continue

            # --- Server Content (audio + text) ---
            server_content = server_msg.get("serverContent")
            if server_content:
                model_turn = server_content.get("modelTurn")
                if model_turn and "parts" in model_turn:
                    for part in model_turn["parts"]:
                        # Audio part — forward to client
                        if "inlineData" in part:
                            inline = part["inlineData"]
                            await client_ws.send_json({
                                "type": "audio",
                                "data": inline.get("data", ""),
                                "mime_type": inline.get("mimeType", "audio/pcm;rate=24000"),
                            })

                        # Text part — forward as transcript
                        if "text" in part:
                            await client_ws.send_json({
                                "type": "transcript",
                                "text": part["text"],
                            })

                # Turn complete signal
                if server_content.get("turnComplete"):
                    await client_ws.send_json({
                        "type": "turn_complete",
                    })

                continue

            # --- Tool Call Interception ---
            tool_call = server_msg.get("toolCall")
            if tool_call:
                # 1. Dispatch to Redis (non-blocking)
                task_id = _dispatch_tool_call(tool_call, api_keys)

                # 2. Notify the UI
                func_calls = tool_call.get("functionCalls", [])
                tool_name = func_calls[0].get("name", "unknown") if func_calls else "unknown"
                await client_ws.send_json({
                    "type": "tool_active",
                    "tool": tool_name,
                    "task_id": task_id,
                })

                # 3. Send immediate toolResponse to Gemini so it keeps talking
                tool_response = {
                    "toolResponse": {
                        "functionResponses": [
                            {
                                "id": func_calls[0].get("id", "") if func_calls else "",
                                "name": tool_name,
                                "response": {
                                    "output": {
                                        "status": "dispatched",
                                        "task_id": task_id,
                                        "message": "Task dispatched to the JARVIS Vision daemon. It is executing now on the physical desktop.",
                                    }
                                },
                            }
                        ]
                    }
                }
                await gemini_ws.send(json.dumps(tool_response))

                logger.info("voice_tool_response_sent", task_id=task_id)
                continue

    except websockets.exceptions.ConnectionClosed as e:
        logger.warning("voice_gemini_connection_closed", code=e.code, reason=str(e.reason)[:100])
    except Exception as e:
        logger.error("voice_gemini_to_client_error", error=str(e)[:200])
    finally:
        session_active.clear()


# ---------------------------------------------------------------------------
# Main WebSocket Endpoint
# ---------------------------------------------------------------------------

@router.websocket("/")
async def voice_stream(websocket: WebSocket):
    """
    Voice OS WebSocket Proxy Endpoint.

    Client connects with: ws://localhost:8000/v1/stream/voice/?gemini_api_key=KEY
    """
    await websocket.accept()

    # Extract the API key from query params
    gemini_api_key = websocket.query_params.get("gemini_api_key", "")
    if not gemini_api_key:
        await websocket.send_json({
            "type": "error",
            "message": "Missing gemini_api_key query parameter.",
        })
        await websocket.close(code=4001, reason="Missing API key")
        return

    api_keys = {"gemini_key": gemini_api_key}
    gemini_uri = _build_gemini_uri(gemini_api_key)
    setup_message = _build_setup_message()

    # --- Resilient connection to Gemini Live API (up to 3 retries) ---
    gemini_ws = None
    last_error = ""

    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            logger.info("voice_gemini_connecting", attempt=attempt)
            gemini_ws = await asyncio.wait_for(
                websockets.connect(
                    gemini_uri,
                    additional_headers={"Content-Type": "application/json"},
                    max_size=16 * 1024 * 1024,  # 16 MB frame limit for audio
                ),
                timeout=GEMINI_CONNECT_TIMEOUT,
            )
            # Send setup frame
            await gemini_ws.send(json.dumps(setup_message))
            logger.info("voice_gemini_connected", attempt=attempt)
            break

        except asyncio.TimeoutError:
            last_error = f"Connection timeout on attempt {attempt}"
            logger.warning("voice_gemini_timeout", attempt=attempt)
        except websockets.exceptions.InvalidStatusCode as e:
            last_error = f"HTTP {e.status_code} on attempt {attempt}"
            logger.warning("voice_gemini_rejected", attempt=attempt, status=e.status_code)
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:100]} on attempt {attempt}"
            logger.warning("voice_gemini_connect_error", attempt=attempt, error=str(e)[:100])

        if attempt < MAX_CONNECT_RETRIES:
            await asyncio.sleep(1.0 * attempt)  # Linear backoff

    if gemini_ws is None:
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to connect to Gemini Live API after {MAX_CONNECT_RETRIES} attempts. {last_error}",
        })
        await websocket.close(code=4002, reason="Gemini connection failed")
        return

    # --- Run bidirectional proxy ---
    session_active = asyncio.Event()
    session_active.set()

    # --- Voice Out Injection ---
    async def _voice_out_listener():
        from redis.asyncio import Redis as AsyncRedis
        async_redis = AsyncRedis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            while session_active.is_set():
                result = await async_redis.blpop("jarvis_voice_out_queue", timeout=1)
                if result:
                    _, payload = result
                    data = json.loads(payload)
                    question = data.get("question", "")
                    if question:
                        logger.info("injecting_clarification_question", question=question)
                        gemini_frame = {
                            "clientContent": {
                                "turns": [
                                    {
                                        "role": "user",
                                        "parts": [{"text": f"[SYSTEM OVERRIDE]: State suspended. The background planner requires your help. Ask the user this concise question aloud: {question}"}]
                                    }
                                ],
                                "turnComplete": True
                            }
                        }
                        await gemini_ws.send(json.dumps(gemini_frame))
        except Exception as e:
            logger.error("voice_out_listener_error", error=str(e))
        finally:
            await async_redis.aclose()

    try:
        await asyncio.gather(
            _client_to_gemini(websocket, gemini_ws, session_active),
            _gemini_to_client(websocket, gemini_ws, session_active, api_keys),
            _voice_out_listener(),
        )
    finally:
        session_active.clear()

        # Clean shutdown of Gemini connection
        try:
            await gemini_ws.close()
        except Exception:
            pass

        # Clean shutdown of client connection
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass

        logger.info("voice_session_terminated")