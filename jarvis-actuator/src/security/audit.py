from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4
import json

from src.models.schemas import ActionContext
from src.security.config import settings


_audit_lock = Lock()


class AuditLogger:
    def __init__(self, audit_dir: Path | None = None, audit_file_name: str | None = None) -> None:
        self.audit_dir = audit_dir or settings.audit_dir
        self.audit_file_name = audit_file_name or settings.audit_file_name

    @property
    def audit_path(self) -> Path:
        return self.audit_dir / self.audit_file_name

    def record(
        self,
        *,
        action: str,
        context: ActionContext,
        allowed: bool,
        message: str,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> str:
        audit_id = str(uuid4())
        event = {
            "audit_id": audit_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "service": settings.service_name,
            "action": action,
            "execution_id": context.execution_id,
            "requested_by": context.requested_by,
            "source": context.source,
            "risk_score": context.risk_score,
            "requires_approval": context.requires_approval,
            "audit_tags": context.audit_tags,
            "allowed": allowed,
            "message": message,
            "metadata": metadata or {},
            "error": error,
        }
        self._append_event(event)
        return audit_id

    def _append_event(self, event: dict[str, Any]) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        with _audit_lock:
            with self.audit_path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
                audit_file.write("\n")


audit_logger = AuditLogger()
