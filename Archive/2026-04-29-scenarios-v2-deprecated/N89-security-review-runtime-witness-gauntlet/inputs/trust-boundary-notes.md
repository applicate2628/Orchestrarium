# Trust Boundary Notes

- request JSON, query strings, and headers are caller-controlled unless bound to authenticated server
  context
- route handlers may receive synthetic tests with harmless example tokens; examples are not live
  secrets unless the code propagates them to a sink
- public `GET /health` endpoints are acceptable when they do not expose secrets or privileged state
- `rel="noopener"` on static documentation links is acceptable hardening, not a vulnerability
- webhook signatures must not be bypassable by debug query strings and must be coupled to replay
  prevention
- audit logs and URLs are durable exposure sinks; putting bearer tokens, cookies, service keys, or
  account emails there is a security finding
