"""Permission enforcement and trusted approval receipts for Tool calls."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ApprovalReceipt:
    """Process-local evidence produced by PermissionHook after user approval."""

    receipt_id: str
    tool_name: str
    issued_at: str
    expires_at: str
    issuer: str = "permission_hook"
    approval_id: str | None = None

    @classmethod
    def issue(cls, tool_name: str, *, lifetime_seconds: int = 300) -> "ApprovalReceipt":
        now = datetime.now(UTC)
        return cls(uuid4().hex, tool_name, now.isoformat(), (now + timedelta(seconds=lifetime_seconds)).isoformat())


ApprovalFunction = Callable[[str, dict[str, Any]], bool | ApprovalReceipt]
ReceiptPersister = Callable[[ApprovalReceipt, dict[str, Any]], str]


class ToolApprovalDeniedError(PermissionError):
    """Raised when a tool requiring user approval is denied."""


class PermissionHook:
    """Enforce approval and attach a receipt to the ephemeral hook context."""

    def __init__(
        self,
        approval_function: ApprovalFunction | None = None,
        receipt_persister: ReceiptPersister | None = None,
    ) -> None:
        self._approval_function = approval_function
        self._receipt_persister = receipt_persister

    def handle(self, event: str, context: dict[str, Any]) -> None:
        if event != "before_tool_call":
            return
        tool = context["tool"]
        if not tool.requires_approval:
            return
        if self._approval_function is None:
            raise ToolApprovalDeniedError(f"tool {tool.name} requires approval")
        decision = self._approval_function(tool.name, context["arguments"])
        if not decision:
            raise ToolApprovalDeniedError(f"tool approval denied: {tool.name}")
        receipt = decision if isinstance(decision, ApprovalReceipt) else ApprovalReceipt.issue(tool.name)
        if receipt.issuer != "permission_hook" or receipt.tool_name != tool.name:
            raise ToolApprovalDeniedError("invalid_approval_receipt")
        try:
            if datetime.fromisoformat(receipt.expires_at) <= datetime.now(UTC):
                raise ToolApprovalDeniedError("expired_approval_receipt")
        except ValueError as exc:
            raise ToolApprovalDeniedError("invalid_approval_receipt") from exc
        if self._receipt_persister is not None:
            receipt = replace(
                receipt,
                approval_id=self._receipt_persister(receipt, context),
            )
        context["approval_receipt"] = receipt
