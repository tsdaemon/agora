import uvicorn

from agora.config import Settings
from agora.server import build_app


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    uvicorn.run(
        build_app(settings),
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",  # only Traefik can reach this container
        server_header=False,
    )


if __name__ == "__main__":
    main()
