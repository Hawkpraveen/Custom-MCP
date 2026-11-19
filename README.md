# Walled AI MCP Guardian

Guardian asks you to approve or block MCP requests before they reach an upstream server. Connect Claude Desktop by local stdio or Claude Web by a remote HTTPS connector. Choose one approval interface: Tkinter or the local web dashboard.

## 1. Prepare Guardian

Requires Python 3.11+. For the web dashboard, also install Node.js 18+ and npm.

Create private credentials:

```powershell
python guardian.py init
```

If you want the web dashboard, build it once:

```powershell
Push-Location src/guardian/ui/react
npm ci
npm run build
Pop-Location
```

## 2. Start an approval interface

Start one option from the project root and leave the terminal running:

```powershell
python scripts/start_local.py --ui tkinter
```

Or, after building the dashboard:

```powershell
python scripts/start_local.py --ui web
```

For web approval, open `http://127.0.0.1:8765/dashboard/` and sign in with `approver_token` from `.guardian/config.json`. Wait for Connected.

## 3. Connect Claude

### Claude Desktop

1. In another terminal at the project root, run `python guardian.py desktop-config`.
2. Merge the printed `mcpServers.guardian-demo` entry into Claude Desktop's `claude_desktop_config.json`. Keep any other entries.
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Fully quit and restart Claude Desktop. Approve Guardian's `tools/list` request when it appears.

### Claude Web

1. Keep Guardian running. In a second terminal, start an authenticated HTTPS tunnel to port `8765` (for example, `ngrok http 8765`).
2. Copy the tunnel's HTTPS address. From the project root, run `python guardian.py web-config --public-url https://YOUR-PUBLIC-HOST`.
3. Open `.guardian/claude-web-connection.txt` locally. It contains the MCP URL and `Authorization` header; keep it private.
4. In Claude, open **Customize → Connectors → Add custom connector**. Enter a name such as **Custom MCP Server** and the generated URL ending in `/mcp`.
5. Choose **No sign-in** and add the generated `Authorization` request header. Guardian uses a fixed bearer token, not OAuth.
6. Connect the new server and approve its `tools/list` request in Guardian.

The tunnel must stay running. Claude Web connects to the public HTTPS address, not localhost. See [Claude's connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) if your account's setup screens differ.

## 4. Test Allow and Block

In Claude Web, ask it to call the record note tool. Approve the first request in Guardian, then block the second:

```text
Use the Record note tool from Custom MCP Server to record exactly ALLOW-my-test-001. Call the tool; don’t just describe it.
```

```text
Use the Record note tool from Custom MCP Server to record exactly BLOCK-my-test-002. Call the tool; don’t just describe it.
```

Use unique note values on later runs. Check `.guardian/executions.jsonl`: the allowed note should appear; the blocked note should not.

## 5. Run automated tests

From the project root:

```powershell
python -m unittest discover -s tests -v
```

For frontend tests, run `npm test` from `src/guardian/ui/react/`.

## Keep credentials private

Do not share `.guardian/`, put tokens in screenshots, or expose the approval dashboard publicly. Guardian controls only traffic routed through it.

More: [web dashboard](docs/web-dashboard.md) · [configuration](docs/configuration.md) · [troubleshooting](docs/troubleshooting.md).
