# Troubleshooting

[Project README](../README.md)

| Problem | Try this |
|---|---|
| `python` is not recognized | Install Python 3.11+ or use its full executable path; reopen the terminal. |
| `ModuleNotFoundError: tkinter` | Install Tcl/Tk support with Python. Tkinter mode needs it; web mode does not. |
| `Can't find a usable init.tcl` | Repair Python's Tcl/Tk installation. Verify with `python -m tkinter`. |
| Web dashboard is not built | From the project root, run `Push-Location src/guardian/ui/react`, `npm ci`, `npm run build`, then `Pop-Location`. |
| `npm ci` cannot download packages | Check network access or use a complete npm cache. Python/Tkinter mode does not need npm. |
| Port 8765 or 8001 is occupied | Stop the previous Guardian process. Do not terminate a process unless you have confirmed it belongs to Guardian. |
| Approval UI says Disconnected | Check that the gateway is running and wait for Connected. Only one UI can hold the lease. |
| A request expires or disappears | Submit it again. Expired or disconnected requests cannot be reused. |
| Dashboard rejects sign-in | Use `approver_token`; other tokens cannot approve. After five failed attempts, wait 30 seconds. |
| Dashboard returns 403 | Use its local loopback URL. Public dashboard access is blocked by design. |
| Claude Desktop shows no tools | Check the merged config JSON and absolute paths, restart Claude fully, and approve `tools/list`. |
| Claude Web cannot connect | Use a public HTTPS endpoint on port 443 and the generated `Authorization` header. Keep the tunnel running. |
| Claude Web has no fixed-header option | Check connector access with the account administrator. Guardian does not implement OAuth. |
| HTTP 401 | Check that the correct token is used for this role. |
| HTTP 403 | Check the configured `allowed_origins` value. |
| HTTP 502 | Check that the configured upstream is running and reachable. |
| Demo ledger is missing | It is created after the first allowed `record_note` call. |

## Existing configuration fails validation

Run `python guardian.py init` and follow the reported field error. The command preserves the file; correct it privately and retry.

## Stale approval interface

Disconnect or quit the active UI before switching modes. After a crash, the default heartbeat lease lasts 120 seconds. Wait for it to expire, then restart Guardian. Pending requests fail closed.

## Optional Tcl/Tk runtime workaround

If Python cannot find `init.tcl`, repairing Python is preferred. For restricted environments, the launcher can use matching `tcl8.6` and `tk8.6` directories under `.guardian/runtime/`. Obtain both from the same Python installation. These machine-specific files are optional and ignored by Git.
