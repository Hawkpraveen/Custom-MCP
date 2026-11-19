# First run

[Project README](../README.md)

## Requirements

- Python 3.11 or newer.
- Tkinter support for the desktop popup.
- Node.js 18+ and npm only if using the web dashboard.
- A public HTTPS endpoint for Claude Web. Claude Desktop uses local stdio.

No third-party Python packages are required. Run commands from the folder containing `guardian.py`.

## Initialize and start

Create private credentials:

```powershell
python guardian.py init
```

For web approval, build the dashboard first:

```powershell
Push-Location src/guardian/ui/react
npm ci
npm run build
Pop-Location
```

Start one approval interface:

```powershell
python scripts/start_local.py --ui tkinter
```

Or:

```powershell
python scripts/start_local.py --ui web
```

For web mode, open `http://127.0.0.1:8765/dashboard/` and sign in with `approver_token` from `.guardian/config.json`. Wait for Connected before connecting a client. Keep the launcher running.

## Try the demo

In a second terminal at the project root:

```powershell
python tools/demo_client.py --transport http
```

Approve `initialize`, `tools/list`, and the `ALLOW:` note. Block the `BLOCK:` note. Check the ledger:

```powershell
Get-Content .guardian/executions.jsonl
```

The allowed note should appear; the blocked note should not. To try stdio, run `python tools/demo_client.py --transport stdio` instead.

## Stop and continue

- Tkinter: choose **Quit and block pending**.
- Web: choose **Disconnect**, then press Ctrl+C in the launcher terminal.
- Run automated checks with `python -m unittest discover -s tests -v`.
- Follow the [Claude setup guide](claude-integration.md) to connect Desktop or Web.

The launcher starts a local demo upstream and the Guardian gateway. See [configuration](configuration.md) for manual startup and custom settings.



