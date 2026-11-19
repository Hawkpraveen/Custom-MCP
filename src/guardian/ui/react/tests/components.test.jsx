import {test} from "node:test";
import assert from "node:assert/strict";
import {renderToStaticMarkup} from "react-dom/server";
import {RequestDetails} from "../src/components/RequestDetails.jsx";
import {RequestQueue} from "../src/components/RequestQueue.jsx";
import {SettingsDialog} from "../src/components/SettingsDialog.jsx";

const item = {id: "request-a", deadline: 100, server: "demo", source: "test", fingerprint: "digest",
  message: {jsonrpc: "2.0", id: 1, method: "tools/call", params: {name: "record_note", arguments: {note: '<img src=x onerror="alert(1)">'}}}};

test("untrusted request arguments render as text rather than HTML", () => {
  const html = renderToStaticMarkup(<RequestDetails item={item} connected busy={false} now={1000} onDecision={() => {}}/>);
  assert.ok(html.includes("&lt;img"));
  assert.ok(!html.includes("<img"));
});

test("expired and disconnected requests disable both decision buttons", () => {
  for (const state of [{connected: false, now: 1000}, {connected: true, now: 100001}]) {
    const html = renderToStaticMarkup(<RequestDetails item={item} busy={false} {...state} onDecision={() => {}}/>);
    assert.equal((html.match(/disabled=""/g) || []).length, 2);
  }
});

test("concurrent requests remain separate selectable queue entries", () => {
  const html = renderToStaticMarkup(<RequestQueue pending={[item, {...item, id: "request-b"}]} selectedId="request-b" onSelect={() => {}}/>);
  assert.equal((html.match(/aria-pressed=/g) || []).length, 2);
  assert.equal((html.match(/aria-pressed="true"/g) || []).length, 1);
});

test("settings expose the configured timeout range and the review notification action", () => {
  const html = renderToStaticMarkup(<SettingsDialog settings={{approval_timeout: 180, min_timeout: 1, max_timeout: 600}}
    saving={false} saveMessage="" onSave={() => {}} notifications={{permission: "default", message: "", enable: () => {}}} onClose={() => {}}/>);
  assert.match(html, /value="180"/);
  assert.match(html, /max="600"/);
  assert.match(html, /Enable desktop notifications/);
  assert.match(html, /Review request/);
});
