# Ideas — the parking lot

TaskFlow is deliberately small. Every feature must earn its place by teaching
something about MCP; anything that would only make the *app* better belongs here
instead of in the codebase.

If you feel the urge to build one of these, add a line explaining what it would
teach. If you can't, that's your answer.

## Product features we are not building

- Sprints / iterations
- Labels and tags
- File attachments
- Notifications and email
- Activity feed / audit log
- Task dependencies, subtasks
- Search
- Time tracking

## MCP ideas that might earn their place later

- **Sampling** — have a tool ask the *client's* model to summarise a project.
  Genuinely interesting, but client support is patchy; series #1 learned this the
  hard way. Only worth it if we can demo it honestly.
- **A second MCP server** — a tiny one (time, or a public fetch server) wired into
  the same chat client, to show the client doesn't care where tools come from.
  `servers.yaml` is already a list for this reason.
- **Elicitation** — the server asking the user a clarifying question mid-tool-call.
  Same caveat as sampling: check real client support before promising anything.
- **Streaming progress notifications** on a long-running tool.

## Infrastructure deferred to a possible series #3

- Kubernetes (kind → managed)
- A real identity provider (Keycloak / OIDC) replacing our own JWTs — see
  [ADR 0002](decisions/0002-own-jwt-instead-of-an-identity-provider.md)
- CI/CD and a deployed public demo
- Observability: tracing a request from chat message to SQL query
