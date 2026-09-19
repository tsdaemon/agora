"""Access-token verification (resource-server side only).

Agora never issues tokens. Keycloak does; FastMCP's JWTVerifier checks signature, issuer and
audience, and this wrapper adds what it does not: `exp` is mandatory and the token must belong to
the single owner. Tokens and claims are never logged.
"""

from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier

from agora.config import Settings


class OwnerTokenVerifier(TokenVerifier):
    def __init__(self, inner: TokenVerifier, owner_subject: str) -> None:
        super().__init__()
        self._inner = inner
        self._owner_subject = owner_subject

    async def verify_token(self, token: str) -> AccessToken | None:
        access = await self._inner.verify_token(token)
        if access is None or access.expires_at is None:
            return None
        if access.subject != self._owner_subject:
            return None
        return access


def build_verifier(settings: Settings, *, public_key: str | None = None) -> OwnerTokenVerifier:
    """Verifier against the Keycloak realm JWKS. `public_key` is for tests only."""
    inner = JWTVerifier(
        public_key=public_key,
        jwks_uri=None if public_key else f"{settings.issuer}/protocol/openid-connect/certs",
        issuer=settings.issuer,
        audience=settings.expected_audience,
        algorithm="RS256",
    )
    return OwnerTokenVerifier(inner, settings.owner_subject)
