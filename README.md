# Agora

A self-hosted [MCP](https://modelcontextprotocol.io) server that lets an AI agent search, create and manage listings on online Ukrainian marketplaces, through one marketplace-neutral tool surface.

**Scope: Ukrainian marketplaces only, for now.** OLX Ukraine (olx.ua) is the first integration. Other Ukrainian marketplaces (Prom, Rozetka, ...) plug in as adapters. Marketplaces in other countries are out of scope.

## Status

Pre-alpha. Design and first task only, no code yet. Python, served over Streamable HTTP, targeting ChatGPT as the client. See [`docs/DESIGN.md`](docs/DESIGN.md) and [`docs/tasks/`](docs/tasks/).

## Goals

- **Official APIs only.** No browser automation and no scraping. If a marketplace has no usable API, it is not supported.
- **Read and write.** Search, fetch details, and create, update and deactivate listings.
- **Images from the conversation.** Photos the user shares in the chat can be staged and attached to a new listing.
- **Safe by default.** Every write needs explicit confirmation, secrets never enter the model's context, and marketplace content is treated as untrusted.
- **Small and boring.** One process, no headless browser, runs in a locked-down container on a home server.

## Non-goals

- Marketplaces outside Ukraine (for now).
- Bypassing anti-bot systems, rate limits or ToS.
- Buying, payments or messaging on the user's behalf (may be reconsidered later).
- A hosted multi-tenant service. Agora is single-user and self-hosted.

## Layout

```
docs/DESIGN.md     architecture, tool surface, security model
docs/tasks/        task ledger (one file per task, index in README)
AGENTS.md          instructions for AI coding agents working on this repo
```

## License

TBD.
