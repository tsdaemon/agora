# Agora design

Status: draft v0. Anything marked `UNVERIFIED` must be confirmed against official marketplace docs before it is relied on.

Scope: Ukrainian marketplaces only, for now. OLX Ukraine (olx.ua) is first. Other countries are out of scope.

## 1. Problem

An AI agent should be able to find items and manage the user's own listings on marketplaces. Existing MCP servers for this scrape sites with a headless browser: heavy, fragile, insecure (sandbox disabled, live untrusted pages) and unable to safely post. Agora talks to official APIs only.

## 2. Principles

1. Official, authenticated APIs. No scraping, no browser.
2. One neutral tool surface. The agent shouldn't need to know which marketplace it is talking to, except where features genuinely differ.
3. Explicit capabilities. An adapter declares what it supports, and unsupported operations fail clearly instead of being emulated.
4. Human-in-the-loop for writes.
5. Least privilege: minimal OAuth scopes, non-root container, and the smallest inbound exposure that ChatGPT's connector model allows (see 5 and 8).

## 3. Architecture

```
MCP client (official ChatGPT, developer-mode custom connector)
        |  Streamable HTTP over public HTTPS, OAuth 2.1 access token
        v
+-------------------------------+
| MCP server (src/server)       |  tool registration, pydantic validation,
|                               |  output sanitising, confirmation gate
+---------------+---------------+
                |
        MarketplaceRegistry
                |
   +------------+------------+
   v            v            v
 OLX adapter  (future)    (future)      src/adapters/<name>/
   |
   v
 HTTP client (httpx) + OAuth token store + rate limiter
```

Modules:

Python package `agora` under `src/agora/`. Paths below are relative to it.

- `src/server/`: MCP wiring, tool definitions, confirmation gate, sanitiser.
- `src/core/`: neutral types (`Listing`, `SearchQuery`, `ListingDraft`, `Money`), the `MarketplaceAdapter` interface, the registry, error types.
- `src/adapters/olx/`: OLX client, auth, mapping between OLX payloads and core types.
- `src/auth/`: OAuth2 helpers and token storage, shared by adapters.
- `src/config/`: env and secret loading, validated with pydantic.

### Adapter interface (sketch)

Shown in TypeScript-style pseudo-notation for brevity. The implementation is a Python `Protocol` with pydantic models.

```ts
interface MarketplaceAdapter {
  readonly id: string;                  // "olx-ua"
  readonly capabilities: Set<Capability>; // search | get | create | update | deactivate | categories | images
  search(q: SearchQuery): Promise<Page<Listing>>;
  get(id: string): Promise<Listing>;
  listCategories(parent?: string): Promise<Category[]>;
  // write operations return a plan first; execute() performs it
  planCreate(draft: ListingDraft): Promise<WritePlan>;
  planUpdate(id: string, patch: ListingPatch): Promise<WritePlan>;
  planDeactivate(id: string): Promise<WritePlan>;
  execute(plan: WritePlan): Promise<Listing | void>;
}
```

Adapter ids name the marketplace (`olx-ua`, later e.g. `prom-ua`). Only Ukrainian marketplaces are supported, so there is no per-country parameterisation of the OLX adapter for now. UNVERIFIED: OLX Ukraine API host, app registration and credentials.

## 4. Tool surface

Marketplace-neutral, all take a `marketplace` argument (an adapter id).

| Tool | Kind | Notes |
|---|---|---|
| `marketplaces_list` | read | Adapters configured, with capabilities |
| `listings_search` | read | query, category, price range, location, sort, page |
| `listings_get` | read | Single listing by id |
| `categories_list` | read | Needed to create a valid listing |
| `my_listings_list` | read | The authenticated user's own listings |
| `images_stage` | write (local only) | Takes a file attached in the ChatGPT conversation (`openai/fileParams`), stores it in a local staging area and returns an `image_id`. No remote write. See 4.1 |
| `listing_create_preview` | plan | Validates a draft and returns a plan plus a confirmation token. No remote write |
| `listing_update_preview` | plan | Same, for updates |
| `listing_deactivate_preview` | plan | Same, for deactivate/delete |
| `write_confirm` | write | Executes a previously previewed plan given its token |

The server uses stateless JSON responses (`stateless_http`, `json_response`): there are no server-initiated messages, so no long-lived SSE stream for Cloudflare or a proxy to buffer or cut.

Two-step writes are deliberate: there is no single tool that mutates remote state from raw agent input. The client is expected to show the preview to the user and get approval before calling `write_confirm`.

### 4.1 Images from the conversation

Goal: the user shares photos in the chat ("sell this, here are the pictures") and the agent attaches them to a new listing.

- Client is the official ChatGPT app. Per OpenAI's docs, a tool declares `_meta["openai/fileParams"]: ["<property>"]` and ChatGPT then passes a file object for that property with `download_url` and `file_id` (required) and `mime_type`, `file_name` (optional). Sources: [Apps SDK reference](https://developers.openai.com/apps-sdk/reference), [OpenAI community thread](https://community.openai.com/t/file-input-parameters-to-tools/1371839).
- `images_stage` declares its `images` property (an array of file objects) as a file param. The server downloads each `download_url`, validates it, stages it and returns an opaque `image_id` per file. The image bytes never pass through the model's context.
- Fetching a URL supplied by a client is an SSRF surface. Require `https`, resolve the host and refuse private, loopback and link-local addresses (re-check after each redirect, or refuse redirects), set connect and total timeouts, and enforce the size cap while streaming. The download URL is treated as a secret and never logged.
- Never accept plain URLs or base64 from the model in place of file params in v1. Add a fallback only if testing shows file params are unreliable.
- Never touches the marketplace at this step.
- `ListingDraft.images` holds `image_id`s, not bytes or URLs. Previews list them so the human sees what will be uploaded.
- Only on `write_confirm` does the adapter upload the staged bytes to the marketplace, in the way its API requires (multipart versus URL: UNVERIFIED for OLX UA, see open question 3).
- Validation at staging: allow-list of types (JPEG, PNG, WebP) by magic bytes, not by filename or claimed MIME. Size and count caps (`AGORA_MAX_IMAGE_BYTES`, `AGORA_MAX_IMAGES_PER_LISTING`). Decode-check the image.
- Privacy: strip EXIF and other metadata (notably GPS location) before storing. Re-encode rather than passing the original through.
- Staged files live in `AGORA_DATA_DIR/staging`, mode 0600, random names, short TTL (default 24 h), deleted after a successful upload. Request body size is capped before reading it fully.
- UNVERIFIED in practice: public reports say file params behave inconsistently across ChatGPT surfaces (mobile uploads sending incomplete references, and some connectors never receiving hydrated file objects; see [apps-sdk-examples#185](https://github.com/openai/openai-apps-sdk-examples/issues/185)). Task 0001 must test with the user's real ChatGPT (web and mobile) and record the result. If unreliable, fallback options are an authenticated `POST /images` upload route the user uses directly, or a tool taking a URL.
- Prompt-injection note: text inside images (OCR-like content the model reads) is untrusted, same as listing text.

## 5. Security model

Threats, in order of concern:

1. **Prompt injection via listing content** driving the agent to post, edit or delete listings, or to leak data.
2. **Credential leakage**: OAuth tokens or client secrets reaching the model, logs or images.
3. **Runaway agent**: loops creating listings or hammering the API and getting the account banned.
4. **Supply chain**: dependency compromise.
5. **Exposure**: server reachable by something it shouldn't be.

Mitigations:

- **Confirmation gate.** `*_preview` tools store the plan server-side, keyed by a random single-use token bound to the exact payload hash, with a short TTL (default 10 min). `write_confirm` accepts only the token, so the payload cannot change between preview and execute. Preview output is what the human reviews.
- **Config-level write switch.** Writes are disabled unless `AGORA_WRITES=enabled`. A per-marketplace and per-day cap on writes (`AGORA_MAX_WRITES_PER_DAY`, default 10).
- **Sanitising.** All remote text is length-limited, control characters stripped, and wrapped in the tool result as data fields. Output never includes upstream error bodies.
- **Secrets.** Read from env or `*_FILE` paths (Docker secrets). Token store on a mounted volume with mode 0600. Redaction of known secret values in logs.
- **Least privilege.** Request the minimum OAuth scopes per operation. Read-only mode requests read scopes only.
- **Rate limiting** and retry with backoff in the shared HTTP client. Honour `Retry-After`. Hard cap on retries.
- **Supply chain.** Few dependencies, pinned, `uv sync --frozen`, lockfile committed, `pip-audit` in CI.
- **Deployment.** Container runs as non-root, read-only rootfs, `--cap-drop ALL`, and the HTTP port reachable only via Traefik. ChatGPT calls the connector from OpenAI's cloud, so the `/mcp` endpoint must be reachable over public HTTPS. Decided: a Cloudflare Tunnel (`cloudflared` on theseus, outbound connection only, no inbound ports or router port forward; Cloudflare terminates TLS and forwards to Traefik on the internal network). No Cloudflare Access policy may sit in front of these hostnames. Every request must carry a valid OAuth access token (section 7), verified for signature, expiry, issuer and audience. Validate `Host` against an allow-list on every route (no cookies or browser-held credentials are used, so an Origin check adds little; FastMCP's own guard covers `/mcp`). Expose only `/mcp` and the OAuth metadata paths. Traefik trusts forwarded headers only from `cloudflared`. Restricting to OpenAI's published egress IPs is UNVERIFIED and probably impractical behind Cloudflare.
- **Egress.** The marketplace API hosts, plus the HTTPS hosts serving ChatGPT file download URLs (UNVERIFIED which; do not hard-code, learn from testing) and the OAuth provider. SSRF guards in 4.1 apply.

## 6. Configuration

Environment variables (secrets via `_FILE` variants):

| Var | Purpose |
|---|---|
| `AGORA_MARKETPLACES` | Comma list of enabled adapters, e.g. `olx-ua` |
| `AGORA_WRITES` | `enabled` to allow writes, otherwise read-only |
| `AGORA_MAX_WRITES_PER_DAY` | Write cap |
| `AGORA_DATA_DIR` | Token store and state |
| `AGORA_PUBLIC_HOST` | Public hostname, no scheme (always served over HTTPS). `https://<host>` is the OAuth audience and base of the metadata URLs, e.g. `agora.example.com` |
| `AGORA_OAUTH_ISSUER` | Keycloak realm issuer URL whose tokens are accepted, e.g. `https://keycloak.example.com/realms/home` |
| `AGORA_OWNER_SUBJECT` | The Keycloak `sub` of the one allowed user |
| `AGORA_PORT`, `AGORA_EXTRA_ALLOWED_HOSTS`, `AGORA_ALLOWED_ORIGINS` | Listen port, extra allowed Host values, allowed Origin values |
| `AGORA_MAX_IMAGE_BYTES`, `AGORA_MAX_IMAGES_PER_LISTING` | Image caps |
| `OLX_UA_CLIENT_ID`, `OLX_UA_CLIENT_SECRET` | OAuth app credentials (UNVERIFIED naming of what OLX issues) |

## 7. Auth

Two separate OAuth relationships.

**ChatGPT to Agora (inbound).** Per OpenAI's [auth docs](https://developers.openai.com/plugins/build/auth), remote MCP servers use OAuth 2.1 (authorization code with PKCE, protected resource metadata at `/.well-known/oauth-protected-resource`, client registration via DCR or CIMD), mTLS (OpenAI-managed), or no auth. ChatGPT cannot present a static API key or bearer token, and does not support client-credentials. So the earlier static bearer token idea is dropped. "No auth" is rejected because the server can write to the user's marketplace account.
Decision: a self-hosted **Keycloak** on theseus is the authorization server (the NAS has 32 GB RAM, so its weight is acceptable). Agora is only a resource server: it never issues tokens and contains no OAuth server code.

- **Identity lives in Keycloak, not in Google.** The owner is a local Keycloak user. Google is attached as an external identity provider (identity brokering) purely as one login method, linked to that existing user. Self-registration is disabled and Google login must not auto-create users. To leave Google later: unlink the provider. Agora is unaffected because it trusts Keycloak's `sub`, never Google's.
- **Break-glass from day one:** give the owner a local credential (passkey, or password plus TOTP) in Keycloak, so losing Google access does not lock out the server.
- **Agora validates** each request's JWT: signature via Keycloak's JWKS, issuer (`AGORA_OAUTH_ISSUER`), audience equal to `https://<AGORA_PUBLIC_HOST>`, expiry, and `sub` equal to `AGORA_OWNER_SUBJECT`. It serves `/.well-known/oauth-protected-resource` pointing at Keycloak as the authorization server.
- **ChatGPT registration:** Keycloak's DCR endpoint (`/realms/<realm>/clients-registrations/openid-connect`), restricted with client registration policies to ChatGPT's redirect URIs. UNVERIFIED: whether ChatGPT needs CIMD instead, and how Keycloak binds the audience (`resource` parameter); an audience mapper may be needed.
- **Exposure:** Keycloak's public surface is limited to the realm's OAuth/OIDC paths. The admin console is not exposed publicly (internal network or VPN only).
- **Hostnames (example values; the real ones live only in the local `.env`):** `keycloak.example.com` and `agora.example.com` (DNS in Cloudflare). OLX callback: `https://agora.example.com/oauth/olx/callback`.
- **Verified with the real ChatGPT (2026-09-19):** DCR works (CIMD off); redirect URI `https://chatgpt.com/connector_platform_oauth_redirect`; PKCE S256; token `aud` = the origin while the metadata `resource` is `<origin>/mcp` (accepted); ChatGPT requires the RFC 8414 metadata URL `/.well-known/oauth-authorization-server/<realm path>` to be publicly reachable. ChatGPT calls from OpenAI's published egress ranges (`https://openai.com/chatgpt-connectors.json`) with an `aiohttp` user agent.
- **Cloudflare:** Bot Fight Mode challenges OpenAI's server-side requests (403 to the client). On the Free plan WAF Skip rules cannot skip it, so it has to be disabled, or the OpenAI ranges allowed by IP Access Rules, or the hostnames moved to a zone without it.
- **Spike first** (task 0002): a ChatGPT connector against Keycloak with a dummy tool must work end to end before marketplace work depends on it.
- **Fallback** if the spike fails: an embedded thin authorization server in Agora, delegating login to Google.
- Other self-hosted options were considered (Authentik, Zitadel, Ory Hydra, Authelia, Pocket ID). Keycloak is the only one confirmed to work as an MCP authorization server; the others are UNVERIFIED for DCR.

**Agora to marketplace (outbound).** OAuth2 per marketplace. For OLX, the developer portal's "Add app" form (Ukrainian UI) asks for app name, website URL, **callback URI (required)** and description. Plan: callback URI is `https://<AGORA_PUBLIC_HOST>/oauth/olx/callback`, served by Agora itself, since it is public anyway. The consent flow is started only from an authenticated owner session, uses a random single-use `state` bound to that session, and the resulting tokens go to the token store, never to the model. Fall back to a `localhost` callback with the CLI only if OLX allows it (UNVERIFIED). The app name entered is "Agora". UNVERIFIED for OLX: which grant types are available (authorization code with user consent versus client credentials), whether refresh tokens are issued, token lifetimes, and whether a private user can register an app. A one-time CLI command (`agora auth <marketplace>`) performs the interactive consent on a machine with a browser and writes tokens to the data dir. The server itself never opens a browser.

## 8. Deployment

Target: the `theseus` home NAS as a Docker container. Transport is Streamable HTTP only: a long-running container behind Traefik with OAuth-protected `/mcp` (section 7), following the existing homelab compose conventions (see the `homelab-compose-deploy` skill). Stdio is not supported.

## 9. Testing

- Unit tests for mapping and the confirmation gate.
- Adapter tests against recorded, scrubbed fixtures. No network in CI.
- A manual smoke script against a real account, never run in CI.

## 10. Open questions

1. Does OLX Ukraine offer API access to a private (non-business) user, and what does registration involve? (blocks task 0001)
2. ~~Which country?~~ Resolved: Ukraine only, for now.
3. Image upload for new listings: what the OLX UA API accepts (URLs versus multipart), and whether ChatGPT file params work reliably for images (see 4.1).
4. Category attribute schemas: OLX categories require category-specific fields. How much of this do we model versus pass through as validated key-value pairs?
5. ~~Language/runtime~~ Resolved: Python 3.12+ with FastMCP (built on the official MCP SDK).
6. ~~Inbound identity provider~~ Decided: Keycloak, with Google as a brokered login method (section 7). Still to verify in the spike: DCR versus CIMD, and audience binding.
7. ~~Public exposure~~ Decided: Cloudflare Tunnel, hostnames `agora.example.com` and `keycloak.example.com`. To test: SSE/streaming behaviour through Cloudflare, and that Cloudflare bot/WAF settings do not block OpenAI.
