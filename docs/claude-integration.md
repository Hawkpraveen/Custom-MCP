# Claude Desktop and Web

[Project README](../README.md)

Choose the connection method that matches the Claude app. Both use the same approval interface: Tkinter or the local web dashboard. Start Guardian and wait for the interface to show Connected first.

## Claude Desktop

Generate a configuration entry on the computer where Claude Desktop runs:

```powershell
python guardian.py desktop-config
```

Merge the generated `mcpServers.guardian-demo` entry into Claude's config, preserving other entries:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Fully quit and restart Claude Desktop. Approve the initial `tools/list` request. Test one allowed and one blocked `record_note` call; verify the ledger in `.guardian/executions.jsonl`.

Generated paths are specific to the current computer and Python interpreter. Regenerate the entry after moving the project or changing Python. To protect another stdio server, replace the upstream command after `--` in the generated entry.

## Claude Web

Claude's remote connector needs a public HTTPS endpoint on port 443; localhost alone cannot be reached from Anthropic's cloud. Start Guardian with either approval UI. If ngrok is not installed and configured, follow its [Windows install and setup guide](https://ngrok.com/download/windows). Then expose port `8765`:

```powershell
ngrok http 8765
```

For a reserved ngrok domain, you can set the public URL explicitly:

```powershell
ngrok http 8765 --url https://YOUR-NAME.ngrok.app
```

Use the HTTPS address ngrok prints, or the reserved address supplied with `--url`, in the command below. Keep Guardian and the tunnel running.

```powershell
python guardian.py web-config --public-url https://YOUR-PUBLIC-HOST
```

The public URL must match the tunnel URL, without a trailing `/mcp`. See ngrok's [URL and endpoint command guide](https://ngrok.com/docs/gateway/agent/cli#ngrok-http).

Open `.guardian/claude-web-connection.txt` locally. It contains the MCP URL and bearer credential; keep it private. In Claude's custom connector:

1. Enter the generated URL ending in `/mcp`.
2. Choose **No sign-in** (Guardian does not implement OAuth).
3. Add the generated `Authorization` request header.
4. Keep **Streamable HTTP** selected.

Keep the approval interface connected. Approve `tools/list`, then test one allowed and one blocked tool call. Confirm the allowed note appears in `.guardian/executions.jsonl` and the blocked note does not.

Cloudflare Quick Tunnels do not support SSE. Use an SSE-capable tunnel such as ngrok if the upstream streams responses. See [Claude's connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Important

- Never put the bearer token in the URL, source code, screenshots, or recordings.
- Remove duplicate direct Claude connections to any upstream you intend to protect.
- Guardian only controls traffic routed through its gateway.
- See [configuration](configuration.md) and [troubleshooting](troubleshooting.md) for help.

