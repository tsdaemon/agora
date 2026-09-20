from typing import Any

import pytest
from pydantic import ValidationError

from agora.draft import ListingDraft

VALID: dict[str, Any] = {
    "title": "Велосипед міський, стан ідеальний",
    "description": "Продаю міський велосипед, користувалися два сезони, без ушкоджень. " * 2,
    "category_id": 123,
    "contact_name": "Anatolii",
    "city_id": 1,
}


def test_valid_draft_gets_defaults() -> None:
    draft = ListingDraft.model_validate(VALID)
    assert draft.advertiser_type == "private"
    assert draft.image_ids == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "too short"),
        ("title", "x" * 151),
        ("description", "short"),
        ("description", "x" * 9001),
        ("category_id", 0),
        ("advertiser_type", "company"),
        ("contact_phone", "call me maybe"),
        ("price", {"value": -1, "currency": "UAH"}),
        ("price", {"value": 10, "currency": "uah"}),
    ],
)
def test_limits_are_enforced(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ListingDraft.model_validate({**VALID, field: value})


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ListingDraft.model_validate({**VALID, "status": "active"})
