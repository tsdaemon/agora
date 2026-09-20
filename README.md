<p align="center">
  <img src="docs/logo.png" alt="Agora logo" width="200">
</p>

<h1 align="center">Agora</h1>

<p align="center">
  <img alt="Status: pre-alpha" src="https://img.shields.io/badge/status-pre--alpha-orange">
  <img alt="Python" src="https://img.shields.io/badge/python-3.x-3776AB?logo=python&logoColor=white">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server-blue">
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-yes-success">
  <img alt="Marketplace: OLX Ukraine" src="https://img.shields.io/badge/marketplace-OLX%20Ukraine-23e5db">
</p>

A self-hosted [MCP](https://modelcontextprotocol.io) server that lets an AI agent create new listings on OLX Ukraine, with photos from the chat, through OLX's official API and behind a confirmation step.

**Scope: OLX Ukraine (olx.ua), creating listings only.** OLX's official API manages your own account and offers no search over other people's listings, so there is no search tool. You can also read your own message threads (read-only). Other marketplaces and countries are out of scope.

## Status

Pre-alpha. A dummy server (`ping` tool) with Keycloak token validation exists, to prove the ChatGPT connector chain. The OLX integration is not built yet. Python and [FastMCP](https://gofastmcp.com), served over Streamable HTTP, targeting ChatGPT as the client. See [`docs/DESIGN.md`](docs/DESIGN.md); tasks are tracked in Notion (Digital Home, project Agora).

## Goals

- **Official APIs only.** No browser automation and no scraping. If a marketplace has no usable API, it is not supported.
- **Create listings.** Look up categories, attributes and locations, preview a draft, then confirm to publish. Read your own listings to check the result.
- **Images from the conversation.** Photos the user shares in the chat can be staged and attached to a new listing.
- **Safe by default.** Every write needs explicit confirmation, secrets never enter the model's context, and marketplace content is treated as untrusted.
- **Small and boring.** One process, no headless browser, runs in a locked-down container on a home server.

## Non-goals

- Marketplaces outside Ukraine (for now).
- Bypassing anti-bot systems, rate limits or ToS.
- Buying, payments or messaging on the user's behalf (may be reconsidered later).
- A hosted multi-tenant service. Agora is single-user and self-hosted.

## Development

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev).

```
cp .env.sample .env    # fill in your values
task setup             # install dependencies
task check             # lint, type-check, test
task dev               # run the server
task deploy            # build and deploy with the overlay
```

## Layout

```
src/agora/         server, auth, config
tests/             pytest suite
docs/FLOWS.md      sequence diagrams of the auth and listing flows
docs/DESIGN.md     architecture, tool surface, security model
AGENTS.md          instructions for AI coding agents working on this repo
```

## License

TBD.
