import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from agora.config import Settings

ISSUER = "https://keycloak.example/realms/home"
ORIGIN = "https://agora.example"
OWNER = "owner-sub"


def _pem(key: rsa.RSAPrivateKey) -> tuple[str, str]:
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private, public


@pytest.fixture(scope="session")
def keypair() -> tuple[str, str]:
    return _pem(rsa.generate_private_key(public_exponent=65537, key_size=2048))


@pytest.fixture(scope="session")
def other_private_key() -> str:
    return _pem(rsa.generate_private_key(public_exponent=65537, key_size=2048))[0]


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {"public_host": "agora.example", "oauth_issuer": ISSUER, "owner_subject": OWNER}
    )


@pytest.fixture
def make_token(keypair: tuple[str, str]) -> Callable[..., str]:
    def _make(
        *,
        key: str | None = None,
        algorithm: str = "RS256",
        drop: tuple[str, ...] = (),
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": ORIGIN,
            "sub": OWNER,
            "azp": "chatgpt-client",
            "iat": now,
            "exp": now + 300,
            "scope": "openid email",
        }
        claims.update(overrides)
        for name in drop:
            claims.pop(name, None)
        return jwt.encode(claims, key or keypair[0], algorithm=algorithm, headers={"kid": "k1"})

    return _make
