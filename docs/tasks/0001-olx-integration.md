# 0001: OLX integration

- Status: todo
- Depends on: 0002 (for the auth and ChatGPT parts; research and core can start first)
- Created: 2026-09-19

## Goal

Ship the first working Agora adapter: OLX Ukraine (olx.ua), through its official API, with search, get, and confirmed create, update and deactivate of the user's own listings. Includes the project scaffold and core needed to host it.

## Acceptance criteria

- [ ] OLX API access is confirmed possible for the user (see step 1), with docs cited in this file.
- [ ] `uv run` test, lint (`ruff`) and type-check (`mypy --strict`) pass in a clean checkout, with no network access in tests.
- [ ] The server starts over Streamable HTTP, rejects requests without a valid OAuth access token, and lists the tools from DESIGN section 4.
- [ ] `listings_search`, `listings_get`, `categories_list` and `my_listings_list` work against the real OLX API for OLX Ukraine.
- [ ] Images shared in the conversation can be staged with `images_stage` (validated, metadata stripped) and attached to a created listing.
- [ ] A listing can be created via `listing_create_preview` then `write_confirm`, and appears on the real account. Update and deactivate work the same way.
- [ ] `write_confirm` rejects unknown, expired, reused and payload-mismatched tokens (tested).
- [ ] With `AGORA_WRITES` unset, all write tools refuse.
- [ ] No tool output or log contains a token or client secret (tested).
- [ ] Container image builds, runs as non-root with a read-only rootfs, and contains no browser.

## Steps

### 1. Research (blocks everything else)

- [ ] Find the official OLX Ukraine developer documentation and record the URLs here.
- [ ] Determine: can a private user register an app? Is approval required?
- [ ] Record auth flow: grant types, scopes, token and refresh lifetimes, redirect URI rules.
- [ ] Record endpoints for: adverts list/search, advert get, advert create/update/deactivate/delete, categories and category attributes, image upload, the user's own adverts.
- [ ] Record rate limits, pagination, error format, and any moderation or publication delay after create.
- [ ] Update DESIGN, replacing each `UNVERIFIED` OLX item with fact plus source.
- [ ] Stop and ask the user if OLX API access is not available. Do not fall back to scraping.

### 2. Scaffold

- [ ] `pyproject.toml`, `uv.lock`, Python 3.12+, `src/agora` layout, ruff, mypy strict, pytest, pinned deps.
- [ ] Update the Commands section in `AGENTS.md`.
- [ ] Config loader with pydantic-settings or plain pydantic and `_FILE` secret support.

### 3. Core

- [ ] Neutral types and `MarketplaceAdapter` interface per DESIGN section 3.
- [ ] Registry and capability checks.
- [ ] Sanitiser for remote text.
- [ ] Confirmation gate: single-use tokens, payload hash binding, TTL, daily write cap, write switch.

### 4. OLX adapter

- [ ] HTTP client with rate limiting, bounded retries, `Retry-After`, redacted logging.
- [ ] OLX OAuth: owner-gated consent flow with callback at `/oauth/olx/callback` (single-use `state`), and a token store with refresh. Check first whether OLX accepts a `localhost` callback.
- [ ] Pydantic models for every OLX response used, with scrubbed fixtures.
- [ ] Read operations: search, get, categories, my listings.
- [ ] Write operations: plan and execute for create, update, deactivate, including image upload.
- [ ] Image staging per DESIGN 4.1: `images_stage`, magic-byte type check, size caps, EXIF stripping, TTL cleanup, body size cap, with tests (non-image with image extension, oversize, EXIF GPS removed, expired staging cleaned).
- [ ] Verify with the real ChatGPT app (web and mobile) that `openai/fileParams` delivers usable `download_url`s for chat-attached images, and decide whether a fallback route is needed (DESIGN 4.1). Record the result here.
- [ ] Mapping between OLX payloads and neutral types, including category attributes (see DESIGN open question 4).

### 5. MCP server

- [ ] Streamable HTTP server exposing the tools in DESIGN section 4 with pydantic input schemas, Keycloak-issued JWT validation (issuer, audience, expiry, single owner `sub`, per DESIGN 7), protected resource metadata, and Origin/Host checks.
- [ ] `images_stage` declares `_meta["openai/fileParams"]`, downloads with SSRF guards (https only, no private addresses, timeouts, streamed size cap), with tests for each guard.
- [ ] Short, actionable error messages, with no upstream bodies.

### 6. Packaging

- [ ] Dockerfile: multi-stage, non-root, read-only rootfs compatible, no browser.
- [ ] Compose example for theseus (use the `homelab-compose-deploy` skill for conventions).
- [ ] README usage section: how to add the server as a custom connector in ChatGPT developer mode.

### 7. Verification

- [ ] Manual smoke test against a real account, with steps written down in `docs/`.
- [ ] `pip-audit` reviewed, and findings that affect production dependencies fixed or justified here.

## Open questions / blockers

- Does the user have, or can they obtain, OLX API credentials? (needs the user)

## Log

- 2026-09-19: Hostnames fixed: `agora.tsd.lol`, `keycloak.tsd.lol`. Tracked in Notion (Digital Home, project Agora) as three tasks: Keycloak, OLX API app registration, OLX MCP server.

- 2026-09-19: Task created. The previous project, the `l-margiela/olx-mcp` fork, was audited and abandoned because it scrapes with Chromium (`--no-sandbox`) and cannot create listings.
- 2026-09-19: Scope narrowed to Ukrainian marketplaces only (OLX UA first). Added image staging for images shared in the conversation (DESIGN 4.1).
- 2026-09-19: Stack decided: Python. Transport decided: Streamable HTTP only (no stdio). Image `path` input dropped because the server is remote.
- 2026-09-19: Client is official ChatGPT. Static bearer token dropped (ChatGPT cannot send one); inbound auth is OAuth 2.1. Images come via `openai/fileParams` download URLs instead of base64. Sources in DESIGN 4.1 and 7.
- 2026-09-19: User will expose the server publicly and prefers Google login over a self-hosted IdP. Google cannot be the authorization server itself for ChatGPT (DCR/CIMD needed), so Agora embeds a thin one delegating login to Google. OLX app registration form needs a callback URI, planned as `<public url>/oauth/olx/callback`.
- 2026-09-19: Inbound auth changed to Keycloak on theseus (Google only as a brokered login), so Agora needs no embedded authorization server. Split out as task 0002.
