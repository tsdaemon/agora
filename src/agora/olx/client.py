"""HTTP client for the OLX Ukraine Partner API.

Base URL, the `Version: 2.0` header and the 4500 requests / 5 minutes / IP limit (403 and a
30 minute block when exceeded) are from the official portal (https://developer.olx.ua/articles/getting-access-to-api
and the spec at https://developer.olx.ua/swagger/v2/partner_api.yaml). Errors raised here are
short and never contain upstream bodies, tokens or request payloads.
"""

import asyncio
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from agora.olx.models import (
    Advert,
    Category,
    CategoryAttribute,
    City,
    District,
    ErrorEnvelope,
    Message,
    Region,
    Thread,
    unwrap,
    unwrap_object,
)

BASE_URL = "https://www.olx.ua/api/partner"
API_VERSION = "2.0"
# Well under OLX's 4500 per 5 minutes; a 403 there means a 30 minute block, so stay far away.
DEFAULT_MAX_REQUESTS = 1000
WINDOW_SECONDS = 300.0
MAX_RETRIES = 2
MAX_RETRY_WAIT = 30.0

TokenProvider = Callable[[], Awaitable[str]]
M = TypeVar("M", bound=BaseModel)


class OlxError(Exception):
    """Failure that is safe to show the model."""


class OlxUnavailable(OlxError):
    pass


class RateLimiter:
    def __init__(
        self,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._max = max_requests
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._hits: deque[float] = deque()

    async def acquire(self) -> None:
        while True:
            now = self._clock()
            while self._hits and now - self._hits[0] >= self._window:
                self._hits.popleft()
            if len(self._hits) < self._max:
                self._hits.append(now)
                return
            await self._sleep(self._window - (now - self._hits[0]))


def _describe(status: int, body: bytes) -> str:
    if status in (401, 403):
        return "OLX rejected the credentials or the request is not allowed. Re-authorise OLX."
    if status == 404:
        return "OLX could not find that item."
    if status == 400 or status == 422:
        try:
            error = ErrorEnvelope.model_validate_json(body).error
            fields = sorted({v.field for v in error.validation if v.field})[:10]
        except ValidationError:
            fields = []
        if fields:
            return "OLX rejected these fields: " + ", ".join(fields) + "."
        return "OLX rejected the request as invalid."
    if status == 429:
        return "OLX rate limit reached. Try again later."
    return "OLX is unavailable right now. Try again later."


class OlxClient:
    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        http: httpx.AsyncClient | None = None,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._token = token_provider
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))
        self._limiter = limiter or RateLimiter()
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        json: dict[str, JsonValue] | None = None,
    ) -> JsonValue:
        # Only idempotent requests are retried; a create is never repeated automatically.
        retries = MAX_RETRIES if method == "GET" else 0
        for attempt in range(retries + 1):
            await self._limiter.acquire()
            headers = {
                "Authorization": f"Bearer {await self._token()}",
                "Version": API_VERSION,
                "Accept": "application/json",
            }
            try:
                response = await self._http.request(
                    method, BASE_URL + path, params=params, json=json, headers=headers
                )
            except httpx.HTTPError as exc:
                if attempt < retries:
                    await self._sleep(min(2.0**attempt, MAX_RETRY_WAIT))
                    continue
                raise OlxUnavailable("Could not reach OLX. Try again later.") from exc
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < retries:
                    await self._sleep(_retry_wait(response, attempt))
                    continue
            if response.status_code >= 400:
                raise OlxError(_describe(response.status_code, response.content))
            if response.status_code == 204 or not response.content:
                return None
            try:
                return TypeAdapter(JsonValue).validate_json(response.content)
            except ValidationError as exc:
                raise OlxError("OLX returned an unreadable response.") from exc
        raise OlxUnavailable("OLX is unavailable right now. Try again later.")  # pragma: no cover

    @staticmethod
    def _parse_list(model: type[M], raw: JsonValue) -> list[M]:
        try:
            return TypeAdapter(list[model]).validate_python(unwrap(raw))  # type: ignore[valid-type]
        except ValidationError as exc:
            raise OlxError("OLX returned an unexpected response shape.") from exc

    @staticmethod
    def _parse_one(model: type[M], raw: JsonValue) -> M:
        try:
            return model.model_validate(unwrap_object(raw))
        except ValidationError as exc:
            raise OlxError("OLX returned an unexpected response shape.") from exc

    async def categories(self, parent_id: int | None = None) -> list[Category]:
        params: dict[str, str | int] | None = None
        if parent_id is not None:
            params = {"parent_id": parent_id}
        return self._parse_list(Category, await self._request("GET", "/categories", params=params))

    async def category_attributes(self, category_id: int) -> list[CategoryAttribute]:
        raw = await self._request("GET", f"/categories/{category_id}/attributes")
        return self._parse_list(CategoryAttribute, raw)

    async def regions(self) -> list[Region]:
        return self._parse_list(Region, await self._request("GET", "/regions"))

    async def cities(self, offset: int = 0, limit: int = 100) -> list[City]:
        raw = await self._request("GET", "/cities", params={"offset": offset, "limit": limit})
        return self._parse_list(City, raw)

    async def districts(self, city_id: int) -> list[District]:
        raw = await self._request("GET", f"/cities/{city_id}/districts")
        return self._parse_list(District, raw)

    async def my_adverts(
        self, offset: int = 0, limit: int = 50, category_ids: list[int] | None = None
    ) -> list[Advert]:
        params: dict[str, str | int] = {"offset": offset, "limit": limit}
        if category_ids:
            params["category_ids"] = ",".join(str(c) for c in category_ids)
        return self._parse_list(Advert, await self._request("GET", "/adverts", params=params))

    async def advert(self, advert_id: int) -> Advert:
        return self._parse_one(Advert, await self._request("GET", f"/adverts/{advert_id}"))

    async def threads(
        self, advert_id: int | None = None, offset: int = 0, limit: int = 50
    ) -> list[Thread]:
        params: dict[str, str | int] = {"offset": offset, "limit": limit}
        if advert_id is not None:
            params["advert_id"] = advert_id
        return self._parse_list(Thread, await self._request("GET", "/threads", params=params))

    async def messages(self, thread_uuid: str) -> list[Message]:
        try:
            thread = uuid.UUID(thread_uuid)
        except ValueError as exc:
            raise OlxError("Thread id must be a UUID from threads_list.") from exc
        raw = await self._request("GET", f"/threads/{thread}/messages")
        return self._parse_list(Message, raw)

    async def create_advert(self, body: dict[str, JsonValue]) -> Advert:
        return self._parse_one(Advert, await self._request("POST", "/adverts", json=body))


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After", "")
    if header.isdigit():
        return min(float(header), MAX_RETRY_WAIT)
    return min(2.0**attempt, MAX_RETRY_WAIT)
