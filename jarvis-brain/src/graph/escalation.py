"""
jarvis-brain/src/graph/escalation.py

Dual-Core Hybrid Automation Orchestrator — Escalation Engine.

This module implements:
  1. Typed exception hierarchy for deterministic Fast-Path failures
  2. O(1) hashmap-based Exception Triage Registry (no if/elif chains)
  3. VLM Computer Use Daemon escalation via Redis queue
  4. Synchronous telemetry listener that streams VLM progress back

Architecture:
  When a Fast-Path tool (Playwright DOM, Actuator subprocess) throws,
  the executor catches it, looks up the exception type in the triage
  registry in O(1), and receives a TriageVerdict instructing it to
  ESCALATE, RETRY, or ABORT.
"""

from __future__ import annotations

import json
import enum
import threading
from typing import Callable, Dict, Optional, Type

from redis import Redis
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logger import logger


# ---------------------------------------------------------------------------
# 1. Typed Exception Hierarchy
# ---------------------------------------------------------------------------

class JarvisExecutionError(Exception):
    """Base class for all JARVIS execution-path exceptions."""
    pass


class SelectorTimeoutError(JarvisExecutionError):
    """Playwright element not found or not visible within the action timeout."""
    pass


class ElementNotInteractableError(JarvisExecutionError):
    """Element exists in DOM but is blocked by an overlay, modal, or disabled state."""
    pass


class AuthenticationWallError(JarvisExecutionError):
    """Login gate, CAPTCHA challenge, or OAuth redirect detected mid-workflow."""
    pass


class NavigationTimeoutError(JarvisExecutionError):
    """Page did not reach networkidle state within the navigation timeout."""
    pass


class UnmappedCanvasError(JarvisExecutionError):
    """Non-DOM graphical surface (WebGL, <canvas>, PDF viewer) that has no selectors."""
    pass


# ---------------------------------------------------------------------------
# 2. Triage Verdict Enum
# ---------------------------------------------------------------------------

class TriageVerdict(str, enum.Enum):
    ESCALATE_TO_VISION = "escalate_to_vision"
    RETRY_FAST_PATH    = "retry_fast_path"
    ABORT              = "abort"


# ---------------------------------------------------------------------------
# 3. Triage Handler Functions
# ---------------------------------------------------------------------------

def _handle_escalate_to_vision(exc: Exception) -> TriageVerdict:
    """The Fast-Path cannot resolve this — hand off to the VLM daemon."""
    logger.info(
        "triage_verdict_escalate",
        exception_type=type(exc).__name__,
        detail=str(exc)[:200],
    )
    return TriageVerdict.ESCALATE_TO_VISION


def _handle_retry_navigation(exc: Exception) -> TriageVerdict:
    """Transient network issue — one retry is worth attempting."""
    logger.info(
        "triage_verdict_retry",
        exception_type=type(exc).__name__,
        detail=str(exc)[:200],
    )
    return TriageVerdict.RETRY_FAST_PATH


def _handle_payload_error(exc: Exception) -> TriageVerdict:
    """Bad payload from the planner — abort and let the planner self-correct."""
    logger.warning(
        "triage_verdict_abort",
        exception_type=type(exc).__name__,
        detail=str(exc)[:200],
    )
    return TriageVerdict.ABORT


# ---------------------------------------------------------------------------
# 4. O(1) Exception Triage Registry (hashmap, NOT if/elif/else)
# ---------------------------------------------------------------------------

EXCEPTION_TRIAGE: Dict[Type[Exception], Callable[[Exception], TriageVerdict]] = {
    # JARVIS typed exceptions → vision escalation
    SelectorTimeoutError:        _handle_escalate_to_vision,
    ElementNotInteractableError: _handle_escalate_to_vision,
    AuthenticationWallError:     _handle_escalate_to_vision,
    UnmappedCanvasError:         _handle_escalate_to_vision,

    # Playwright native exceptions bubble as TimeoutError / RuntimeError
    TimeoutError:                _handle_escalate_to_vision,
    RuntimeError:                _handle_escalate_to_vision,

    # Transient navigation issues
    NavigationTimeoutError:      _handle_retry_navigation,

    # Planner generated bad payload references
    KeyError:                    _handle_payload_error,
    TypeError:                   _handle_payload_error,
}


def triage_exception(exc: Exception) -> TriageVerdict:
    """
    O(1) exception classification.

    Walks the MRO (Method Resolution Order) of the exception so that
    subclasses of registered types are correctly routed without needing
    explicit entries for every leaf class.
    """
    for cls in type(exc).__mro__:
        handler = EXCEPTION_TRIAGE.get(cls)
        if handler is not None:
            return handler(exc)

    # Unregistered exception types default to escalation —
    # it's safer to let the VLM try than to silently fail.
    logger.warning(
        "triage_unregistered_exception",
        exception_type=type(exc).__name__,
        detail=str(exc)[:200],
    )
    return TriageVerdict.ESCALATE_TO_VISION


# ---------------------------------------------------------------------------
# 5. VLM Escalation Payload Schema
# ---------------------------------------------------------------------------

class VisionEscalationPayload(BaseModel):
    """Typed, validated payload pushed to jarvis_computer_use_queue."""
    task_id: str
    objective: str
    failed_step: str = Field(description="The DAG step ID that triggered escalation")
    failed_tool: str = Field(description="The tool_name that failed")
    failure_reason: str = Field(description="Stringified exception message")
    handover_context: Dict = Field(
        default_factory=dict,
        description="Browser session state from ContextHandoverManager",
    )
    api_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="API keys forwarded so the VLM daemon can authenticate",
    )


# ---------------------------------------------------------------------------
# 6. Redis VLM Escalation + Telemetry Listener
# ---------------------------------------------------------------------------

# Lazy singleton Redis connection (reuses brain's existing Redis infra)
_redis_conn: Optional[Redis] = None
_redis_lock = threading.Lock()

COMPUTER_USE_QUEUE = "jarvis_computer_use_queue"
TELEMETRY_CHANNEL  = "jarvis_telemetry"
VISION_TIMEOUT_SEC = 120  # max seconds to wait for VLM daemon to finish


def _get_redis() -> Redis:
    """Thread-safe lazy Redis connection matching the brain's configured port."""
    global _redis_conn
    if _redis_conn is None:
        with _redis_lock:
            if _redis_conn is None:
                _redis_conn = Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    health_check_interval=10,
                    socket_timeout=120,
                    retry_on_timeout=True
                )
    return _redis_conn


def escalate_to_vision_daemon(payload: VisionEscalationPayload) -> Dict:
    """
    Push the escalation payload to the Computer Use Daemon queue,
    then block-listen on the telemetry Pub/Sub channel until the
    daemon reports success/failure or the timeout expires.

    Returns a dict with the VLM daemon's final status and telemetry.
    """
    conn = _get_redis()

    # 1. Push objective + context to the daemon's intake queue
    message = payload.model_dump_json()
    conn.rpush(COMPUTER_USE_QUEUE, message)

    logger.info(
        "vision_escalation_dispatched",
        task_id=payload.task_id,
        failed_step=payload.failed_step,
        failed_tool=payload.failed_tool,
    )

    # 2. Subscribe to telemetry channel and collect frames
    pubsub = conn.pubsub()
    pubsub.subscribe(TELEMETRY_CHANNEL)

    telemetry_frames: list[dict] = []
    final_status = "timeout"

    try:
        # Block-listen with a per-message timeout of 2 seconds,
        # up to the total VISION_TIMEOUT_SEC budget
        import time
        deadline = time.monotonic() + VISION_TIMEOUT_SEC

        for raw_msg in pubsub.listen():
            if time.monotonic() > deadline:
                logger.warning("vision_telemetry_timeout", task_id=payload.task_id)
                break

            if raw_msg["type"] != "message":
                continue

            try:
                frame = json.loads(raw_msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            # Only process telemetry for our specific task
            if frame.get("task_id") != payload.task_id:
                continue

            telemetry_frames.append(frame)
            status = frame.get("status", "")

            logger.info(
                "vision_telemetry_frame",
                task_id=payload.task_id,
                status=status,
            )

            # Terminal states — stop listening
            if status in ("success", "failed", "CLARIFICATION_NEEDED"):
                final_status = status
                break

    finally:
        pubsub.unsubscribe(TELEMETRY_CHANNEL)
        pubsub.close()

    return {
        "vision_status": final_status,
        "telemetry_frames": telemetry_frames,
        "frame_count": len(telemetry_frames),
    }


def shutdown_escalation():
    """Release the Redis connection pool. Called from tools.py teardown."""
    global _redis_conn
    if _redis_conn is not None:
        _redis_conn.close()
        _redis_conn = None
