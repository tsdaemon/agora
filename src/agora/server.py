"""MCP server wiring: Streamable HTTP, OAuth resource server, tools."""

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider, TokenVerifier
from pydantic import AnyHttpUrl
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp

from agora.auth import build_verifier
from agora.config import Settings


def build_server(settings: Settings, verifier: TokenVerifier | None = None) -> FastMCP:
    auth = RemoteAuthProvider(
        token_verifier=verifier or build_verifier(settings),
        authorization_servers=[AnyHttpUrl(settings.issuer)],
        base_url=settings.origin,
    )
    mcp = FastMCP(
        "Agora",
        instructions="Assistant for the owner's own listings on Ukrainian marketplaces.",
        auth=auth,
    )

    @mcp.tool
    def ping() -> str:
        """Check that the connection and authentication work."""
        return "pong"

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> Response:
        return PlainTextResponse("ok")

    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def protected_resource(_: Request) -> Response:
        # Path-less variant, as documented by OpenAI. The path-aware one
        # (/.well-known/oauth-protected-resource/mcp) is served by FastMCP.
        return JSONResponse(
            {
                "resource": f"{settings.origin}/mcp",
                "authorization_servers": [settings.issuer],
                "bearer_methods_supported": ["header"],
            }
        )

    return mcp


def build_app(settings: Settings, verifier: TokenVerifier | None = None) -> ASGIApp:
    hosts = [settings.public_host, *settings.extra_allowed_hosts]
    return build_server(settings, verifier).http_app(
        path="/mcp",
        transport="streamable-http",
        # One user, no server-initiated messages: stateless JSON responses need no SSE stream,
        # so nothing for Cloudflare or a proxy to buffer or cut.
        stateless_http=True,
        json_response=True,
        # Host allow-list for every route (FastMCP's own guard only covers /mcp). Loopback is
        # for the container healthcheck.
        middleware=[
            Middleware(
                TrustedHostMiddleware,
                allowed_hosts=[*hosts, "127.0.0.1", "localhost"],
            )
        ],
        allowed_hosts=hosts,
        allowed_origins=settings.allowed_origins,
    )
