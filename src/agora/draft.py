"""The listing draft the agent proposes, validated before a preview is issued.

Limits come from OLX's official Partner API spec (https://developer.olx.ua/swagger/v2/partner_api.yaml,
POST /adverts, read 2026-09-20). Category-specific `attributes` are kept as plain code to value
pairs here; their exact wire format and per-category validation are checked in the OLX client
against `GET /categories/{id}/attributes` (UNVERIFIED until then, do not guess it here).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Price(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float = Field(ge=0)
    # OLX requires an uppercase currency code.
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    negotiable: bool = False
    trade: bool = False


class ListingDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=16, max_length=150)
    description: str = Field(min_length=80, max_length=9000)
    # Must be a leaf category (checked against `is_leaf` by the OLX client).
    category_id: int = Field(gt=0)
    advertiser_type: Literal["private", "business"] = "private"
    contact_name: str = Field(min_length=1, max_length=100)
    contact_phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,20}$")
    city_id: int = Field(gt=0)
    # Required by OLX when the city has districts (checked by the OLX client).
    district_id: int | None = Field(default=None, gt=0)
    price: Price | None = None
    attributes: dict[str, str | list[str]] = Field(default_factory=dict)
    # Opaque ids returned by `images_stage`, never bytes or URLs.
    image_ids: list[str] = Field(default_factory=list, max_length=50)
