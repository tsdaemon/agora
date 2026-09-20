"""Confirmation gate for remote writes.

A `*_preview` tool stores a plan here and returns a random single-use token. `write_confirm`
presents only the token, so the payload cannot change between preview and execution: the stored
plan is frozen, hashed at issue time and re-hashed at consume time. State is in memory, so a
restart forgets pending tokens and resets the daily count (the TTL is minutes; persisting the
count is a possible later hardening).
"""

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, JsonValue


class GateError(Exception):
    """Refusal that is safe to show the model: short, actionable, no internals."""


class WritesDisabled(GateError):
    def __init__(self) -> None:
        super().__init__("Writes are disabled on this server (AGORA_WRITES is not enabled).")


class UnknownToken(GateError):
    def __init__(self) -> None:
        super().__init__(
            "Unknown, expired or already used confirmation token. Run the preview again."
        )


class DailyLimitReached(GateError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"Daily write limit of {limit} reached. Try again tomorrow (UTC).")


class PayloadMismatch(GateError):
    def __init__(self) -> None:
        super().__init__(
            "The stored plan no longer matches what was previewed. Run the preview again."
        )


class WritePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: str
    payload: dict[str, JsonValue]
    # Human-readable description shown in the preview; not part of the hash.
    summary: str = ""


@dataclass(frozen=True)
class Issued:
    token: str
    expires_at: datetime
    payload_hash: str


@dataclass
class _Pending:
    plan: WritePlan
    payload_hash: str
    expires_at: datetime


def payload_hash(plan: WritePlan) -> str:
    canonical = json.dumps(
        {"action": plan.action, "payload": plan.payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class ConfirmationGate:
    def __init__(
        self,
        *,
        writes_enabled: bool,
        ttl: timedelta = timedelta(minutes=10),
        max_writes_per_day: int = 10,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._writes_enabled = writes_enabled
        self._ttl = ttl
        self._max_per_day = max_writes_per_day
        self._clock = clock
        self._pending: dict[str, _Pending] = {}
        self._day: date = clock().date()
        self._count = 0

    def issue(self, plan: WritePlan) -> Issued:
        """Store `plan` and return its single-use token. Refuses while writes are disabled."""
        if not self._writes_enabled:
            raise WritesDisabled
        now = self._clock()
        self._purge(now)
        frozen = WritePlan.model_validate(plan.model_dump(mode="json"))  # deep copy
        digest = payload_hash(frozen)
        token = secrets.token_urlsafe(32)
        expires_at = now + self._ttl
        self._pending[token] = _Pending(frozen, digest, expires_at)
        return Issued(token, expires_at, digest)

    def consume(self, token: str) -> WritePlan:
        """Return the plan for `token` and invalidate it. Counts one write against the cap."""
        if not self._writes_enabled:
            raise WritesDisabled
        now = self._clock()
        self._roll_day(now)
        pending = self._pending.get(token)
        if pending is None or pending.expires_at <= now:
            self._pending.pop(token, None)
            raise UnknownToken
        if self._count >= self._max_per_day:
            # Token stays valid: the owner may confirm it after the limit resets.
            raise DailyLimitReached(self._max_per_day)
        del self._pending[token]
        if payload_hash(pending.plan) != pending.payload_hash:
            raise PayloadMismatch
        self._count += 1
        return pending.plan

    def _purge(self, now: datetime) -> None:
        for token in [t for t, p in self._pending.items() if p.expires_at <= now]:
            del self._pending[token]

    def _roll_day(self, now: datetime) -> None:
        if now.date() != self._day:
            self._day = now.date()
            self._count = 0
