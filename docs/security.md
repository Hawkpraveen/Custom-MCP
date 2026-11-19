# Security

[Project README](../README.md)

## Trust and scope

Guardian protects requests routed through its gateway only. Direct Claude connectors or direct access to an upstream bypass it. The OS account, Guardian host, Python interpreter, and configured upstream are trusted.

## Credentials

- Keep `.guardian/config.json` and `.guardian/claude-web-connection.txt` private.
- Guardian uses separate MCP, producer, and approver tokens. Do not reuse or publish them.
- Never put credentials in URLs, frontend code, screenshots, or recordings.
- Claude Web requires a public HTTPS endpoint for MCP. Keep the approval dashboard local.
- Do not expose the bundled demo server publicly.

## Approval handling

- Requests are frozen and fingerprinted while pending.
- An Allow decision applies once to the matching request. Block, cancellation, timeout, expiry, or approver disconnect prevents forwarding.
- Pending decisions are stored in memory and are lost on restart.
- After an approved request reaches the upstream, Guardian cannot roll back its effects or safely retry it.
- Request contents appear in the approval UI. The demo ledger intentionally stores test note text; general audit logs omit parameters and credentials.

## Dashboard protections

The dashboard is loopback-only. It uses an in-memory session, HttpOnly cookie, CSRF checks, same-origin validation, a restrictive content policy, and rate-limited sign-in. It has no remote OAuth login. Block `/dashboard` and `/dashboard/*` at any public reverse proxy.

See the official [MCP security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).
