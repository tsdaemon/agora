"""Environment configuration, validated at startup."""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
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
    # Writes are refused unless this is exactly "enabled".
    writes: str = ""
    max_writes_per_day: int = Field(default=10, ge=1)
    data_dir: Path = Path("/data")
    max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_images_per_listing: int = Field(default=10, ge=1, le=50)

    @property
    def writes_enabled(self) -> bool:
        return self.writes == "enabled"

    @property
    def origin(self) -> str:
        return f"https://{self.public_host}"

    @property
    def issuer(self) -> str:
        return str(self.oauth_issuer).rstrip("/")

    @property
    def expected_audience(self) -> str:
        return self.audience or self.origin


class OlxSettings(BaseSettings):
    """OLX app credentials. Each value may come from `<NAME>` or a file named by `<NAME>_FILE`."""

    model_config = SettingsConfigDict(env_prefix="OLX_", extra="ignore")

    client_id: str = Field(default="", repr=False)
    client_secret: SecretStr = SecretStr("")
    client_id_file: Path | None = None
    client_secret_file: Path | None = None

    @model_validator(mode="after")
    def _read_files(self) -> "OlxSettings":
        if self.client_id_file is not None:
            self.client_id = self.client_id_file.read_text().strip()
        if self.client_secret_file is not None:
            self.client_secret = SecretStr(self.client_secret_file.read_text().strip())
        if not self.client_id or not self.client_secret.get_secret_value():
            raise ValueError("OLX_CLIENT_ID and OLX_CLIENT_SECRET (or *_FILE) are required")
        return self
