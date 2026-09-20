"""Pydantic models for OLX Partner API payloads.

Shapes come from the official spec's component schemas (https://developer.olx.ua/swagger/v2/partner_api.yaml,
read 2026-09-20). Models ignore unknown fields (OLX may add some) but every field we rely on is
declared. Enum-like fields are plain strings so a new value from OLX does not break parsing.
UNVERIFIED: whether list endpoints other than `GET /adverts` wrap their array in `{"data": ...}`;
`unwrap` accepts both until a real response is recorded.
"""

from pydantic import BaseModel, ConfigDict, Field, JsonValue


def unwrap(value: JsonValue) -> JsonValue:
    """Accept either a bare list or `{"data": [...]}`."""
    if isinstance(value, dict) and "data" in value:
        return value["data"]
    return value


def unwrap_object(value: JsonValue) -> JsonValue:
    """Accept either a bare object or `{"data": {...}}`."""
    if isinstance(value, dict) and set(value) == {"data"}:
        return value["data"]
    return value


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Category(_Model):
    id: int
    name: str
    parent_id: int | None = None
    photos_limit: int | None = None
    is_leaf: bool | None = None


class AttributeValue(_Model):
    code: str
    label: str = ""


class AttributeValidation(_Model):
    type: str | None = None
    required: bool = False
    numeric: bool = False
    # The spec types `min` as integer and `max` as string; kept loose on purpose.
    min: int | str | None = None
    max: int | str | None = None
    allow_multiple_values: bool = False


class CategoryAttribute(_Model):
    code: str
    label: str
    unit: str | None = None
    validation: AttributeValidation = Field(default_factory=AttributeValidation)
    values: list[AttributeValue] = Field(default_factory=list)


class Region(_Model):
    id: int
    name: str


class City(_Model):
    id: int
    name: str
    region_id: int | None = None
    county: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class District(_Model):
    id: int
    name: str
    city_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class Contact(_Model):
    name: str = ""
    phone: str | None = None


class Location(_Model):
    city_id: int
    district_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class Image(_Model):
    url: str


class Price(_Model):
    value: float | None = None
    currency: str | None = None
    negotiable: bool = False
    trade: bool = False
    budget: bool = False


class AdvertAttribute(_Model):
    code: str
    value: str | None = None
    values: list[str] | None = None


class Advert(_Model):
    id: int
    status: str
    url: str
    title: str
    description: str
    created_at: str
    activated_at: str | None = None
    valid_to: str | None = None
    category_id: int | None = None
    advertiser_type: str | None = None
    external_id: str | None = None
    external_url: str | None = None
    contact: Contact | None = None
    location: Location | None = None
    images: list[Image] = Field(default_factory=list)
    price: Price | None = None
    attributes: list[AdvertAttribute] = Field(default_factory=list)


class Thread(_Model):
    uuid: str
    advert_id: int | None = None
    interlocutor_id: int | None = None
    total_count: int = 0
    unread_count: int = 0
    created_at: str | None = None
    is_favourite: bool = False


class Attachment(_Model):
    name: str | None = None
    url: str | None = None


class Message(_Model):
    uuid: str
    thread_uuid: str | None = None
    created_at: str | None = None
    type: str
    text: str = ""
    is_read: bool = False
    attachments: list[Attachment] = Field(default_factory=list)


class ErrorDetail(_Model):
    field: str = ""
    title: str = ""
    detail: str = ""


class ErrorBody(_Model):
    status: int | None = None
    title: str = ""
    detail: str = ""
    validation: list[ErrorDetail] = Field(default_factory=list)


class ErrorEnvelope(_Model):
    error: ErrorBody


class TokenResponse(_Model):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str | None = None
    scope: str | None = None
