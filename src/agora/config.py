"""Environment configuration, validated at startup."""

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGORA_", extra="ignore")

    # Public hostname, e.g. agora.example.com (no scheme, no path). Always served over HTTPS;
    # https://<host> is the OAuth audience and the base of the metadata URLs.
    public_host: str = Field(pattern=r"^[A-Za-z0-9.-]+(:[0-9]+)?$")
    # Keycloak realm issuer, e.g. https://keycloak.example.com/realms/home.
    # Compared exactly with the token's `iss`.
    oauth_issuer: AnyHttpUrl
    # Keycloak `sub` of the single user allowed to call this server.
    owner_subject: str = Field(min_length=1)
    # Expected `aud`. Keycloak ignores the RFC 8707 `resource` parameter and always issues the
    # audience set on the `agora-audience` client scope, which is the public origin.
    audience: str | None = None
    # Extra Host header values accepted, e.g. the LAN name agora.lan.example.
    extra_allowed_hosts: list[str] = []
    allowed_origins: list[str] = ["https://chatgpt.com", "https://chat.openai.com"]
    host: str = "0.0.0.0"  # noqa: S104 - container listen address, only Traefik reaches it
    port: int = 6492

    @property
    def origin(self) -> str:
        return f"https://{self.public_host}"

    @property
    def issuer(self) -> str:
        return str(self.oauth_issuer).rstrip("/")

    @property
    def expected_audience(self) -> str:
        return self.audience or self.origin
