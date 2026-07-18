from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentguard.models import PolicyDecision


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    approval_id: str
    request_call_id: str
    session_id: str
    tool_name: str
    arguments_digest: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    severity: str
    reason: str
    matched_rule: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    token: str | None = None


def arguments_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ApprovalManager:
    def __init__(self, token_ttl: timedelta = timedelta(minutes=10)) -> None:
        self.token_ttl = token_ttl
        self._requests: dict[str, ApprovalRequest] = {}
        self._token_index: dict[str, str] = {}

    def create(
        self,
        *,
        call_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        decision: PolicyDecision,
    ) -> ApprovalRequest:
        digest = arguments_digest(arguments)
        for request in self._requests.values():
            if (
                request.status is ApprovalStatus.PENDING
                and request.session_id == session_id
                and request.tool_name == tool_name
                and request.arguments_digest == digest
            ):
                return request
        request = ApprovalRequest(
            approval_id=f"apr_{uuid4().hex[:12]}",
            request_call_id=call_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments_digest=digest,
            severity=decision.severity,
            reason=decision.reason,
            matched_rule=decision.matched_rule,
        )
        self._requests[request.approval_id] = request
        return request

    def approve(self, approval_id: str, now: datetime | None = None) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status is not ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval_id}")
        issued_at = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        updated = request.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "token": token,
                "expires_at": issued_at + self.token_ttl,
            }
        )
        self._requests[approval_id] = updated
        self._token_index[token] = approval_id
        return updated

    def reject(self, approval_id: str) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status is not ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval_id}")
        updated = request.model_copy(update={"status": ApprovalStatus.REJECTED})
        self._requests[approval_id] = updated
        return updated

    def authorize(
        self,
        *,
        token: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        now: datetime | None = None,
    ) -> ApprovalRequest:
        approval_id = self._token_index.get(token)
        if approval_id is None:
            raise ValueError("Unknown approval token")
        request = self.get(approval_id)
        current_time = now or datetime.now(UTC)
        if request.expires_at is None or current_time >= request.expires_at:
            expired = request.model_copy(update={"status": ApprovalStatus.EXPIRED, "token": None})
            self._requests[approval_id] = expired
            self._token_index.pop(token, None)
            raise ValueError("Approval token has expired")
        if request.status is not ApprovalStatus.APPROVED:
            raise ValueError("Approval token is no longer usable")
        if request.session_id != session_id or request.tool_name != tool_name:
            raise ValueError("Approval token scope does not match the tool call")
        if request.arguments_digest != arguments_digest(arguments):
            raise ValueError("Tool arguments changed after approval")

        consumed = request.model_copy(update={"status": ApprovalStatus.CONSUMED, "token": None})
        self._requests[approval_id] = consumed
        self._token_index.pop(token, None)
        return consumed

    def get(self, approval_id: str) -> ApprovalRequest:
        try:
            return self._requests[approval_id]
        except KeyError as exc:
            raise KeyError(f"Unknown approval request: {approval_id}") from exc

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        requests = list(self._requests.values())
        if status is not None:
            requests = [request for request in requests if request.status is status]
        return sorted(requests, key=lambda item: item.created_at, reverse=True)
