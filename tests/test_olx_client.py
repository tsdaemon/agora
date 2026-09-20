"""OLX client tests. Payloads are synthetic, written from the official spec's schemas."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from agora.draft import ListingDraft
from agora.olx.client import OlxClient, OlxError, OlxUnavailable, RateLimiter
from agora.olx.mapping import advert_body

Handler = Callable[[httpx.Request], httpx.Response]
SECRET_TOKEN = "tok-very-secret"
THREAD = "0b0f1c6e-3c36-4a3e-9d0e-6f3f1d2b7a11"
ADVERT: dict[str, Any] = {
    "id": 7,
    "status": "active",
    "url": "https://www.olx.ua/d/uk/obyavlenie/x",
    "title": "Велосипед міський, стан ідеальний",
    "description": "d" * 80,
    "created_at": "2026-09-20T10:00:00+03:00",
    "category_id": 123,
    "contact": {"name": "A"},
    "location": {"city_id": 1},
    "images": [{"url": "https://example.com/i.jpg"}],
    "attributes": [{"code": "state", "value": "used"}],
}


async def token() -> str:
    return SECRET_TOKEN


async def no_sleep(_: float) -> None:
    return None


def make(handler: Handler) -> OlxClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OlxClient(token, http=http, sleep=no_sleep)


async def test_sends_auth_and_version_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"id": 1, "name": "Транспорт", "is_leaf": False}])

    categories = await make(handler).categories(parent_id=5)
    assert categories[0].name == "Транспорт"
    request = seen[0]
    assert request.headers["Authorization"] == f"Bearer {SECRET_TOKEN}"
    assert request.headers["Version"] == "2.0"
    assert request.url.params["parent_id"] == "5"
    assert str(request.url).startswith("https://www.olx.ua/api/partner/categories")


async def test_accepts_bare_list_and_data_wrapper() -> None:
    bare = make(lambda _: httpx.Response(200, json=[{"id": 1, "name": "r"}]))
    wrapped = make(lambda _: httpx.Response(200, json={"data": [{"id": 1, "name": "r"}]}))
    assert (await bare.regions())[0].id == (await wrapped.regions())[0].id == 1


async def test_attributes_parse_values_and_validation() -> None:
    body = [
        {
            "code": "state",
            "label": "Стан",
            "validation": {"type": "attribute", "required": True, "min": 1, "max": "5"},
            "values": [{"code": "new", "label": "Новий"}],
        }
    ]
    client = make(lambda _: httpx.Response(200, json=body))
    attribute = (await client.category_attributes(9))[0]
    assert attribute.validation.required
    assert attribute.values[0].code == "new"


async def test_my_adverts_uses_data_wrapper_and_filters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [ADVERT]})

    adverts = await make(handler).my_adverts(category_ids=[1, 2])
    assert adverts[0].status == "active"
    assert seen[0].url.params["category_ids"] == "1,2"


async def test_unknown_status_value_still_parses() -> None:
    advert = {**ADVERT, "status": "some_new_status"}
    client = make(lambda _: httpx.Response(200, json={"data": advert}))
    assert (await client.advert(7)).status == "some_new_status"


async def test_messages_rejects_non_uuid_thread_id() -> None:
    client = make(lambda _: httpx.Response(200, json=[]))
    with pytest.raises(OlxError, match="UUID"):
        await client.messages("../adverts/1")


async def test_messages_parse() -> None:
    body = [{"uuid": THREAD, "type": "received", "text": "Ще продається?", "is_read": False}]
    client = make(lambda _: httpx.Response(200, json=body))
    assert (await client.messages(THREAD))[0].text == "Ще продається?"


async def test_create_posts_body_and_is_never_retried() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(OlxError):
        await make(handler).create_advert({"title": "t"})
    assert len(calls) == 1
    assert json.loads(calls[0].content) == {"title": "t"}


async def test_get_retries_5xx_then_succeeds() -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json=[])])
    client = make(lambda _: next(responses))
    assert await client.regions() == []


async def test_get_retry_is_bounded() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"Retry-After": "1"})

    with pytest.raises(OlxError):
        await make(handler).regions()
    assert calls == 3


async def test_403_is_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, text="blocked for 30 minutes")

    with pytest.raises(OlxError, match="Re-authorise"):
        await make(handler).regions()
    assert calls == 1


async def test_validation_error_names_fields_only() -> None:
    body = {
        "error": {
            "status": 400,
            "title": "Invalid request",
            "detail": "secret upstream detail",
            "validation": [
                {"field": "title", "title": "Too short", "detail": "echoed user text"},
                {"field": "price", "title": "x", "detail": "y"},
            ],
        }
    }
    with pytest.raises(OlxError) as info:
        await make(lambda _: httpx.Response(400, json=body)).create_advert({})
    message = str(info.value)
    assert message == "OLX rejected these fields: price, title."
    assert "secret upstream" not in message and "echoed" not in message


async def test_errors_never_contain_token_or_upstream_body() -> None:
    client = make(lambda _: httpx.Response(500, text=f"boom {SECRET_TOKEN}"))
    with pytest.raises(OlxError) as info:
        await client.regions()
    assert SECRET_TOKEN not in str(info.value)
    assert "boom" not in str(info.value)


async def test_network_failure_becomes_short_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure for internal-host", request=request)

    with pytest.raises(OlxUnavailable) as info:
        await make(handler).regions()
    assert "internal-host" not in str(info.value)


async def test_unreadable_json_is_an_error() -> None:
    with pytest.raises(OlxError, match="unreadable"):
        await make(lambda _: httpx.Response(200, content=b"<html>")).regions()


async def test_wrong_shape_is_an_error() -> None:
    with pytest.raises(OlxError, match="unexpected"):
        await make(lambda _: httpx.Response(200, json=[{"nope": 1}])).regions()


async def test_rate_limiter_waits_when_window_is_full() -> None:
    now = 0.0
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        nonlocal now
        slept.append(seconds)
        now += seconds

    limiter = RateLimiter(max_requests=2, window=10.0, clock=lambda: now, sleep=sleep)
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    assert slept == [10.0]


def test_advert_body_maps_draft() -> None:
    draft = ListingDraft.model_validate(
        {
            "title": "Велосипед міський, стан ідеальний",
            "description": "d" * 80,
            "category_id": 123,
            "contact_name": "A",
            "contact_phone": "+380501234567",
            "city_id": 1,
            "district_id": 4,
            "price": {"value": 5000, "currency": "UAH", "negotiable": True},
            "attributes": {"state": "used", "features": ["a", "b"]},
        }
    )
    body = advert_body(draft, ["https://example.com/1.jpg"])
    assert body["location"] == {"city_id": 1, "district_id": 4}
    assert body["contact"] == {"name": "A", "phone": "+380501234567"}
    assert body["attributes"] == [
        {"code": "features", "values": ["a", "b"]},
        {"code": "state", "value": "used"},
    ]
    assert body["images"] == [{"url": "https://example.com/1.jpg"}]
    assert body["price"] == {"value": 5000, "currency": "UAH", "negotiable": True, "trade": False}


def test_advert_body_omits_empty_optionals() -> None:
    draft = ListingDraft.model_validate(
        {
            "title": "Велосипед міський, стан ідеальний",
            "description": "d" * 80,
            "category_id": 123,
            "contact_name": "A",
            "city_id": 1,
        }
    )
    body = advert_body(draft, [])
    assert "images" not in body and "price" not in body
    assert body["contact"] == {"name": "A"}
