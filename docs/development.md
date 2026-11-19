# Development and tests

[Project README](../README.md)

## Project layout

- `src/guardian/authorization/`: request state and approval decisions.
- `src/guardian/gateway/`: stdio and HTTP relays.
- `src/guardian/http/`: local authenticated service.
- `src/guardian/ui/tkinter/` and `src/guardian/ui/react/`: approval interfaces.
- `src/guardian/ui/react/`: React dashboard source and build scripts.
- `tests/`: Python integration and protocol tests.

## Run tests

From the project root:

```powershell
python -m unittest discover -s tests -v
```

For frontend tests, run `npm test` from `src/guardian/ui/react/`. Build the dashboard with `npm ci` and `npm run build` there.

Tests cover approval and denial, real execution gating, timeouts, disconnections, concurrent requests, authentication, and dashboard behavior. They do not require a live Claude account. They do not prove Claude Desktop compatibility or the popup's always-on-top behavior.

## Protocol and safety limits

- Guardian forwards requests; it is not an MCP protocol translator.
- `initialize` and the custom `server/discover` handshake are forwarded automatically. Other gated requests need approval.
- Only requests routed through Guardian are controlled.
- Pending approvals are in memory and are not restored after restart.
- Upstream effects cannot be rolled back after a request is forwarded.
- HTTP uploads require `Content-Length`; JSON-RPC batches are unsupported. SSE responses are streamed.
- The bundled demo server writes test notes to `.guardian/executions.jsonl`.

See [architecture](architecture.md) and [security](security.md).


