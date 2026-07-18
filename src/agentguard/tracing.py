from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentguard.models import TraceEvent

REDACTED = "[REDACTED]"


class TraceCollector:
    def __init__(
        self, trace_id: str, session_id: str, output_dir: Path, canaries: set[str]
    ) -> None:
        self.trace_id = trace_id
        self.session_id = session_id
        self.output_dir = output_dir
        self.canaries = canaries
        self.events: list[TraceEvent] = []
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.output_dir / f"{self.trace_id}.jsonl"

    def emit(self, event_type: str, payload: dict[str, Any]) -> TraceEvent:
        sanitized = self._sanitize(payload)
        event = TraceEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            trace_id=self.trace_id,
            session_id=self.session_id,
            type=event_type,
            payload=sanitized,
        )
        self.events.append(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        return event

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, set):
            return sorted(self._sanitize(item) for item in value)
        if isinstance(value, str):
            sanitized = value
            for canary in self.canaries:
                if canary in sanitized:
                    digest = hashlib.sha256(canary.encode()).hexdigest()[:12]
                    sanitized = sanitized.replace(canary, f"{REDACTED}:sha256:{digest}")
            return sanitized
        return value

    def contains_raw_canary(self) -> bool:
        if not self.path.exists():
            return False
        content = self.path.read_text(encoding="utf-8")
        return any(canary in content for canary in self.canaries)
