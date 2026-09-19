import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from agora.auth import build_verifier
from agora.config import Settings
from agora.server import build_app

MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(method: str, params: dict[str, Any] | None = None, id_: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


@pytest.fixture
def client(settings: Settings, keypair: tuple[str, str]) -> Iterator[TestClient]:
    app = build_app(settings, build_verifier(settings, public_key=keypair[1]))
    with TestClient(app, base_url="https://agora.example") as test_client:
        yield test_client


def test_no_token_gets_401_pointing_at_metadata(client: TestClient) -> None:
    response = client.post("/mcp", headers=MCP_HEADERS, json=rpc("tools/list"))
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer")
    assert "resource_metadata=" in challenge
    assert "/.well-known/oauth-protected-resource" in challenge


def test_bad_token_gets_401(client: TestClient) -> None:
    headers = {**MCP_HEADERS, "Authorization": "Bearer nope"}
    assert client.post("/mcp", headers=headers, json=rpc("tools/list")).status_code == 401


def test_non_owner_token_gets_401(client: TestClient, make_token: Callable[..., str]) -> None:
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {make_token(sub='intruder')}"}
    assert client.post("/mcp", headers=headers, json=rpc("tools/list")).status_code == 401


@pytest.mark.parametrize(
    "path", ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"]
)
def test_protected_resource_metadata(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "https://agora.example/mcp"
    assert body["authorization_servers"] == ["https://keycloak.example/realms/home"]


def test_healthz_is_open(client: TestClient) -> None:
    assert client.get("/healthz").text == "ok"


def test_unknown_host_is_rejected(client: TestClient, make_token: Callable[..., str]) -> None:
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
    headers = {**MCP_HEADERS, "Host": "evil.example", "Authorization": f"Bearer {make_token()}"}
    assert client.post("/mcp", headers=headers, json=rpc("tools/list")).status_code == 400


def test_ping_with_valid_token(client: TestClient, make_token: Callable[..., str]) -> None:
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {make_token()}"}
    init = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        ),
    )
    assert init.status_code == 200, init.text
    call = client.post(
        "/mcp",
        headers=headers,
        json=rpc("tools/call", {"name": "ping", "arguments": {}}, id_=2),
    )
    assert call.status_code == 200, call.text
    assert "pong" in json.dumps(call.json())
