# Configuration

[Project README](../README.md)

## Create or reuse settings

```powershell
python guardian.py init
```

The private file is `.guardian/config.json`. `init` creates it if missing, validates it if present, and never replaces existing tokens. Keep `.guardian/` private and out of Git.

## Main settings

| Setting | Purpose |
|---|---|
| `broker_url` | Approval service address; defaults to loopback port `8765`. |
| `approver_token` | Signs in to the Tkinter or web approval interface. |
| `mcp_token` | Authenticates Claude Web requests to Guardian. |
| `producer_token` | Authenticates local stdio gateways. |
| `approval_timeout` | Request decision deadline; default 90 seconds, range 1â€“600. |
| `allowed_origins` | Allowed browser origins; default is `https://claude.ai`. |
| `upstream_url` | Fixed HTTP upstream; defaults to the local demo on port `8001`. |
| `upstream_token` | Optional credential for the HTTP upstream. |
| `server_name` | Label shown for requests from the HTTP upstream. |
| `lease_seconds` | Approval-interface heartbeat lease; default 120 seconds. |
| `capacity` | Maximum pending requests; default 128. |

Tokens must be distinct. Remote URLs must use HTTPS. Keep the upstream address under operator control.

## Common commands

| Command | Use |
|---|---|
| `python scripts/start_local.py --ui tkinter` | Start the demo gateway with the desktop popup. |
| `python scripts/start_local.py --ui web` | Start the demo gateway with the web dashboard. |
| `python guardian.py desktop-config` | Generate a Claude Desktop stdio entry. |
| `python guardian.py web-config --public-url https://HOST` | Generate private Claude Web connector details. |
| `python tools/demo_client.py --transport http` | Try the HTTP approval flow. |
| `python tools/demo_client.py --transport stdio` | Try the stdio approval flow. |

Use `python guardian.py --help` for the full command list.

## Custom configuration

Create a separate file with `python guardian.py init --config .guardian/custom.json`. Pass the same `--config` value to `serve`, `ui`, and the gateway client. The combined launcher uses the default configuration only.

## Generated data

| File | Contents |
|---|---|
| `.guardian/config.json` | Settings and private credentials. |
| `.guardian/executions.jsonl` | Demo notes that actually executed. |
| `.guardian/claude-web-connection.txt` | Generated private URL and bearer header. |
| `.guardian/local.log` | Combined launcher logs. |

