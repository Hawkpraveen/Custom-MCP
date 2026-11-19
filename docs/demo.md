# Demo recording checklist

Use non-sensitive notes. Hide private config files and connector credential fields before recording.

1. Show the running approval app and the configured Guardian tool in the real Claude client.
2. Ask Claude to invoke `record_note` with a unique note, such as `approved-desktop-001`.
3. Show the popup's server, method, tool, arguments, and request ID. Before clicking Allow, show that the execution ledger does not contain the note and Claude has no tool result yet.
4. Click Allow. Show Claude's tool result and the new ledger entry.
5. Ask Claude to invoke the tool with `blocked-desktop-001`. Click Block. Show the denial in Claude and the absence of that note in the ledger.
6. Repeat approval and blocking from Claude Web using the public HTTPS connector.
7. Demonstrate simultaneous pending requests using the transport test client or automated integration tests; approve one and deny the other. Be explicit about which client generated this part.
8. Quit the approval app, then attempt another call. Show that the operation is rejected and no ledger entry appears.
9. Show the test command and summarize the known coverage limitation: only traffic routed through Guardian is controlled.

The local demo client can rehearse the popup flow, but the final video should include real Claude clients to substantiate the assignment's compatibility criteria.

## Compatibility record

| Environment | Status | Evidence |
|---|---|---|
| Windows / Python 3.11.5 local stdio | Automated tests pass | `tests/test_stdio.py` |
| Windows / Python 3.11.5 local HTTP | Automated tests pass | `tests/test_http.py` |
| Windows native popup | Process starts and heartbeat connects; visual verification pending | Interactive check still required |
| React dashboard routes | Automated tests pass | Login, CSRF/Origin/Host validation, exclusive ownership, real Allow/Block execution |
| React components | Automated tests pass; browser visual check unavailable in this environment | Text escaping, disabled expired/offline actions, concurrent queue entries |
| Claude Desktop / Windows | Not tested | Pending |
| Claude Desktop / macOS | Not tested | Pending |
| Claude Web / Chrome on Windows | Manually verified 2026-11-18 | User walkthrough via ngrok; tool discovery, allowed `record_note`, blocked `record_note`, denied result in Claude, and blocked note absent from execution ledger |
| Claude Web / another browser | Not tested | Pending |


