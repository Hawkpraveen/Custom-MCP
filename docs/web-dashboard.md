# Web dashboard

[Project README](../README.md)

The dashboard is an optional local approval UI. Only one interface (Tkinter or web) can be connected at a time.

## Build

Requires Node.js 18+ and npm. From the project root:

```powershell
Push-Location src/guardian/ui/react
npm ci
npm run build
Pop-Location
```

## Run

```powershell
python guardian.py init
python scripts/start_local.py --ui web
```

Open `http://127.0.0.1:8765/dashboard/` and sign in with `approver_token` from `.guardian/config.json`. Wait for Connected before connecting Claude. Keep the dashboard open while requests are pending.

## Decisions and settings

- Review the displayed server, method, arguments, and request ID before choosing Allow or Block.
- Each Allow applies to one request. Disconnect blocks pending requests.
- Settings can change the deadline for new requests (1–600 seconds).
- Optional browser notifications show a review link; they do not appear inside Claude.

## Limits

- The dashboard is loopback-only and has no remote OAuth sign-in.
- Browser background throttling can delay heartbeats; expired requests fail closed.
- Web mode does not provide an always-on-top popup. Use Tkinter when that behavior is required.
- If exposing Claude's MCP endpoint publicly, block `/dashboard` and `/dashboard/*` at the reverse proxy.

For token or connection problems, see [troubleshooting](troubleshooting.md).
