from datetime import UTC, datetime, timedelta

import pytest

from agora.gate import (
    ConfirmationGate,
    DailyLimitReached,
    PayloadMismatch,
    UnknownToken,
    WritePlan,
    WritesDisabled,
    payload_hash,
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def plan(title: str = "Bicycle for sale") -> WritePlan:
    return WritePlan(action="create", payload={"title": title, "tags": ["a", "b"]}, summary="s")


def gate(clock: Clock, **kwargs: object) -> ConfirmationGate:
    options: dict[str, object] = {"writes_enabled": True, "clock": clock, **kwargs}
    return ConfirmationGate(**options)  # type: ignore[arg-type]


def test_issue_then_consume_returns_the_plan() -> None:
    g = gate(Clock())
    issued = g.issue(plan())
    assert g.consume(issued.token).payload == plan().payload


def test_token_is_single_use() -> None:
    g = gate(Clock())
    token = g.issue(plan()).token
    g.consume(token)
    with pytest.raises(UnknownToken):
        g.consume(token)


def test_unknown_token_is_rejected() -> None:
    with pytest.raises(UnknownToken):
        gate(Clock()).consume("nope")


def test_expired_token_is_rejected() -> None:
    clock = Clock()
    g = gate(clock, ttl=timedelta(minutes=10))
    token = g.issue(plan()).token
    clock.now += timedelta(minutes=10)
    with pytest.raises(UnknownToken):
        g.consume(token)


def test_payload_changes_after_preview_do_not_reach_execution() -> None:
    g = gate(Clock())
    original = plan()
    token = g.issue(original).token
    original.payload["title"] = "Something else"  # dict is mutable even on a frozen model
    assert g.consume(token).payload["title"] == "Bicycle for sale"


def test_tampered_stored_plan_is_detected() -> None:
    g = gate(Clock())
    token = g.issue(plan()).token
    stored = g._pending[token].plan  # noqa: SLF001
    stored.payload["title"] = "Tampered"
    with pytest.raises(PayloadMismatch):
        g.consume(token)


def test_hash_binds_action_and_payload_but_not_summary() -> None:
    base = plan()
    assert payload_hash(base) == payload_hash(base.model_copy(update={"summary": "other"}))
    assert payload_hash(base) != payload_hash(base.model_copy(update={"action": "update"}))
    assert payload_hash(base) != payload_hash(plan("Different title"))


def test_writes_disabled_refuses_issue_and_consume() -> None:
    off = ConfirmationGate(writes_enabled=False)
    with pytest.raises(WritesDisabled):
        off.issue(plan())
    with pytest.raises(WritesDisabled):
        off.consume("anything")


def test_daily_cap_blocks_then_resets_next_day() -> None:
    clock = Clock()
    g = gate(clock, max_writes_per_day=1)
    first, second = g.issue(plan()).token, g.issue(plan()).token
    g.consume(first)
    with pytest.raises(DailyLimitReached):
        g.consume(second)
    clock.now += timedelta(days=1)
    # The second token is still inside its TTL only if the TTL allows; use a fresh one.
    g2 = g.issue(plan()).token
    assert g.consume(g2).action == "create"


def test_refused_confirm_over_cap_keeps_token_valid() -> None:
    clock = Clock()
    g = gate(clock, max_writes_per_day=1, ttl=timedelta(days=2))
    first, second = g.issue(plan()).token, g.issue(plan()).token
    g.consume(first)
    with pytest.raises(DailyLimitReached):
        g.consume(second)
    clock.now += timedelta(days=1)
    assert g.consume(second).action == "create"


def test_tokens_are_unique_and_long() -> None:
    g = gate(Clock())
    tokens = {g.issue(plan()).token for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 43 for t in tokens)
