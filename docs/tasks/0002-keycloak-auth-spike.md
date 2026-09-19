# 0002: Keycloak and ChatGPT auth spike

- Status: todo
- Depends on: none
- Created: 2026-09-19

Tracked in Notion (Digital Home, project Agora) as "Keycloak on theseus (auth for Agora)", which holds the full handover. Hostnames: `keycloak.tsd.lol`, `agora.tsd.lol`.

## Goal

Prove that a ChatGPT custom connector can authenticate against a self-hosted Keycloak on theseus and call a protected MCP tool. This gates the auth design in DESIGN section 7. See also the user's Notion task "Add Keycloak to play with external OAuth".

## Acceptance criteria

- [ ] Keycloak runs on theseus (compose overlay per the `homelab-compose-deploy` skill), on its own database, non-root where possible, with the admin console not publicly reachable.
- [ ] A realm with one owner user, self-registration off, a local credential (passkey or password plus TOTP), and Google linked as an identity provider that does not auto-create users.
- [ ] A dummy MCP server (a single `ping` tool) behind Traefik at a public HTTPS hostname, validating Keycloak JWTs (issuer, audience, expiry, owner `sub`).
- [ ] ChatGPT (developer mode connector) completes login and calls `ping`. Requests without a valid token get 401 with correct metadata.
- [ ] Login works with both Google and the local credential, and still works after unlinking Google.
- [ ] Recorded in this file: DCR versus CIMD (which ChatGPT used), how the audience is set, client registration policies used, and any Keycloak version quirks.
- [ ] Also verify `openai/fileParams` on a dummy tool: what ChatGPT sends for an attached image on web and mobile (see DESIGN 4.1).

## Steps

- [ ] Compose overlay, Traefik routes (realm paths only), backups of Keycloak's database.
- [ ] Realm, user, Google IdP, registration policies.
- [ ] Dummy MCP server with JWT validation.
- [ ] Connect from ChatGPT, record results.

## Open questions / blockers

- Google Cloud OAuth client for Keycloak's Google login. (needs the user)
- If DCR or audience binding cannot be made to work: fall back to an embedded authorization server (DESIGN 7 fallback) and record why.

## Log

- 2026-09-19: Task created.
