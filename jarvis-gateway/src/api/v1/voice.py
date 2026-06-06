from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import collections
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.websocket("/")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()
    # O(1) Memory bound buffer (approx 10 seconds of 16kHz audio)
    audio_buffer = collections.deque(maxlen=3200) 
    
    try:
        while True:
            data = await websocket.receive_bytes()
            audio_buffer.append(data)
            
    except WebSocketDisconnect:
        logger.info("voice_socket_closed_gracefully")
    except Exception as e:
        logger.error("voice_socket_crash", error=str(e))
    finally:
        audio_buffer.clear()
        del audio_buffer
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()