from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
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


class ApprovalStore(Protocol):
    def create(
        self,
        *,
        call_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        decision: PolicyDecision,
    ) -> ApprovalRequest: ...

    def approve(self, approval_id: str, now: datetime | None = None) -> ApprovalRequest: ...

    def reject(self, approval_id: str) -> ApprovalRequest: ...

    def authorize(
        self,
        *,
        token: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        now: datetime | None = None,
    ) -> ApprovalRequest: ...

    def get(self, approval_id: str) -> ApprovalRequest: ...

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]: ...


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


class SQLiteApprovalManager:
    """Process-safe approval store shared by the API and MCP gateway."""

    def __init__(self, path: Path, token_ttl: timedelta = timedelta(minutes=10)) -> None:
        self.path = path
        self.token_ttl = token_ttl
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

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
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM approvals
                WHERE status = ? AND session_id = ? AND tool_name = ? AND arguments_digest = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (ApprovalStatus.PENDING.value, session_id, tool_name, digest),
            ).fetchone()
            if row is not None:
                return self._from_row(row)
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
            connection.execute(
                """
                INSERT INTO approvals (
                    approval_id, request_call_id, session_id, tool_name, arguments_digest,
                    status, severity, reason, matched_rule, created_at, expires_at, token_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.approval_id,
                    request.request_call_id,
                    request.session_id,
                    request.tool_name,
                    request.arguments_digest,
                    request.status.value,
                    request.severity,
                    request.reason,
                    request.matched_rule,
                    request.created_at.isoformat(),
                    None,
                    None,
                ),
            )
        return request

    def approve(self, approval_id: str, now: datetime | None = None) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status is not ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval_id}")
        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + self.token_ttl
        token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, expires_at = ?, token_hash = ?
                WHERE approval_id = ?
                """,
                (
                    ApprovalStatus.APPROVED.value,
                    expires_at.isoformat(),
                    self._token_hash(token),
                    approval_id,
                ),
            )
        return request.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "expires_at": expires_at,
                "token": token,
            }
        )

    def reject(self, approval_id: str) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status is not ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval_id}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE approvals SET status = ? WHERE approval_id = ?",
                (ApprovalStatus.REJECTED.value, approval_id),
            )
        return request.model_copy(update={"status": ApprovalStatus.REJECTED})

    def authorize(
        self,
        *,
        token: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        now: datetime | None = None,
    ) -> ApprovalRequest:
        token_hash = self._token_hash(token)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE token_hash = ? LIMIT 1", (token_hash,)
            ).fetchone()
            if row is None:
                raise ValueError("Unknown approval token")
            request = self._from_row(row)
            current_time = now or datetime.now(UTC)
            if request.expires_at is None or current_time >= request.expires_at:
                connection.execute(
                    "UPDATE approvals SET status = ?, token_hash = NULL WHERE approval_id = ?",
                    (ApprovalStatus.EXPIRED.value, request.approval_id),
                )
                raise ValueError("Approval token has expired")
            if request.status is not ApprovalStatus.APPROVED:
                raise ValueError("Approval token is no longer usable")
            if request.session_id != session_id or request.tool_name != tool_name:
                raise ValueError("Approval token scope does not match the tool call")
            if request.arguments_digest != arguments_digest(arguments):
                raise ValueError("Tool arguments changed after approval")
            connection.execute(
                "UPDATE approvals SET status = ?, token_hash = NULL WHERE approval_id = ?",
                (ApprovalStatus.CONSUMED.value, request.approval_id),
            )
        return request.model_copy(update={"status": ApprovalStatus.CONSUMED, "token": None})

    def get(self, approval_id: str) -> ApprovalRequest:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown approval request: {approval_id}")
        return self._from_row(row)

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        with self._connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM approvals ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                ).fetchall()
        return [self._from_row(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    request_call_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    matched_rule TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    token_hash TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_token_hash ON approvals(token_hash)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ApprovalRequest:
        return ApprovalRequest(
            approval_id=row["approval_id"],
            request_call_id=row["request_call_id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            arguments_digest=row["arguments_digest"],
            status=ApprovalStatus(row["status"]),
            severity=row["severity"],
            reason=row["reason"],
            matched_rule=row["matched_rule"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=(datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None),
            token=None,
        )
