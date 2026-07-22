# 0002 — Issue our own JWTs instead of running an identity provider

**Status:** accepted · **Date:** 2026-07-22

## The question

Both the backend and the MCP server need to know who is making a request. We
could run a real identity provider (Keycloak, Auth0, Authentik) and make both
services OAuth 2.1 resource servers, or the backend could issue its own tokens.

## The decision

**The backend issues its own JWTs**, signed HS256 with a shared secret. Login is
`POST /auth/login` with an email and password; out comes a token. The MCP server
verifies that same token and forwards it onward.

An identity provider becomes an optional later phase, not a prerequisite.

## Why

**The teaching goal beats the production goal.** This repo's job is to make a
reader understand MCP. Keycloak is a container, a realm configuration, a
discovery document, PKCE, dynamic client registration, and a token exchange — it
is a week of material *before* the reader writes a single tool. Our whole auth
implementation is about eighty lines they can read in one sitting: hash a
password, sign a token, verify a token, look up the user.

**It's the same shape either way.** From the MCP server's point of view nothing
changes: read a bearer token from the request, verify it, forward it to the
backend. Swapping the issuer later means changing *who signs* and *how we verify*
— the architecture around it is untouched. That is a good thing to be able to
demonstrate, and it's a much better post once readers already understand the
system they're upgrading.

**Series #1 already covers the hard version.** The Moodle project did full OAuth
2.1, a Keycloak realm as code, protected resource metadata, and dynamic client
registration in depth. Repeating it here would be worse than linking to it.

## Notable detail: roles are not in the token

The JWT carries `sub`, `email`, `iat`, and `exp`. It does **not** carry roles.

Roles live in the `project_members` table and are looked up per request. This
means promoting someone to admin takes effect immediately, rather than the next
time they log in — and it means a stolen token can't carry stale elevated
privileges. It costs one indexed query per request, which is the right trade.

## What it costs

**No refresh tokens, no revocation.** A token is valid until it expires (12 hours
by default). There is no logout that actually invalidates anything server-side. We
say so plainly in the post rather than implying otherwise.

**A shared secret between two services.** `JWT_SECRET` must match in the backend
and the MCP server. That coupling is documented loudly in `.env.example`. An
asymmetric key (RS256) would remove it — the MCP server would only need the public
key — and that's exactly what the later IdP phase brings.

**Password handling is ours.** bcrypt via `passlib`, and the usual rules: never
log the password, never return the hash, constant-time comparison. Fine at this
size, but "don't roll your own auth" is real advice and we'll acknowledge that
we're rolling our own *for the purpose of showing how it works*.

## See also

- `PLAN.md` §6 — the auth path, end to end
- ADR 0001 — why the MCP server forwards the user's token rather than holding its own
