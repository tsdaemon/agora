import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable

import pytest

from agora.auth import OwnerTokenVerifier, build_verifier
from agora.config import Settings
from tests.conftest import ISSUER, ORIGIN, OWNER


@pytest.fixture
def verifier(settings: Settings, keypair: tuple[str, str]) -> OwnerTokenVerifier:
    return build_verifier(settings, public_key=keypair[1])


async def test_valid_owner_token(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str]
) -> None:
    access = await verifier.verify_token(make_token())
    assert access is not None
    assert access.subject == "owner-sub"
    assert access.client_id == "chatgpt-client"


async def test_audience_may_be_a_list(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str]
) -> None:
    token = make_token(aud=["account", "https://agora.example"])
    assert await verifier.verify_token(token) is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example/realms/home"},
        {"iss": "https://keycloak.example/realms/home/"},
        {"aud": "https://other.example"},
        {"aud": "https://agora.example/mcp"},
        {"exp": int(time.time()) - 10},
        {"sub": "someone-else"},
    ],
)
async def test_rejects_bad_claims(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str], overrides: dict[str, object]
) -> None:
    assert await verifier.verify_token(make_token(**overrides)) is None


@pytest.mark.parametrize("missing", ["exp", "aud", "sub", "iss"])
async def test_rejects_missing_claims(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str], missing: str
) -> None:
    assert await verifier.verify_token(make_token(drop=(missing,))) is None


async def test_rejects_token_signed_by_another_key(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str], other_private_key: str
) -> None:
    assert await verifier.verify_token(make_token(key=other_private_key)) is None


async def test_rejects_hmac_signed_with_public_key(
    verifier: OwnerTokenVerifier, make_token: Callable[..., str], keypair: tuple[str, str]
) -> None:
    # Algorithm confusion: HS256 token "signed" with the public key as the shared secret.
    # PyJWT refuses to build this, so forge it by hand.
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "k1"}).encode())
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": ORIGIN, "sub": OWNER, "exp": now + 300}
    payload = b64(json.dumps(claims).encode())
    signature = hmac.new(
        keypair[1].encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    assert await verifier.verify_token(f"{header}.{payload}.{b64(signature)}") is None


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c", "eyJhbGciOiJub25lIn0.e30."])
async def test_rejects_garbage(verifier: OwnerTokenVerifier, token: str) -> None:
    assert await verifier.verify_token(token) is None
