from pathlib import Path

import pytest
from pydantic import ValidationError

from agora.config import OlxSettings, Settings


def test_writes_disabled_by_default(settings: Settings) -> None:
    assert not settings.writes_enabled


def test_writes_need_the_exact_word(settings: Settings) -> None:
    assert not settings.model_copy(update={"writes": "true"}).writes_enabled
    assert settings.model_copy(update={"writes": "enabled"}).writes_enabled


def test_olx_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLX_CLIENT_ID", "id-1")
    monkeypatch.setenv("OLX_CLIENT_SECRET", "s3cret")
    olx = OlxSettings()
    assert olx.client_id == "id-1"
    assert olx.client_secret.get_secret_value() == "s3cret"


def test_olx_credentials_from_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "id").write_text("id-2\n")
    (tmp_path / "secret").write_text("file-secret\n")
    monkeypatch.delenv("OLX_CLIENT_ID", raising=False)
    monkeypatch.delenv("OLX_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("OLX_CLIENT_ID_FILE", str(tmp_path / "id"))
    monkeypatch.setenv("OLX_CLIENT_SECRET_FILE", str(tmp_path / "secret"))
    olx = OlxSettings()
    assert (olx.client_id, olx.client_secret.get_secret_value()) == ("id-2", "file-secret")


def test_olx_secret_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLX_CLIENT_ID", "id-3")
    monkeypatch.setenv("OLX_CLIENT_SECRET", "topsecretvalue")
    assert "topsecretvalue" not in repr(OlxSettings())


def test_olx_credentials_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLX_CLIENT_ID", raising=False)
    monkeypatch.delenv("OLX_CLIENT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        OlxSettings()
