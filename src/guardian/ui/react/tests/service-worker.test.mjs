import {test} from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import vm from "node:vm";

const script = await readFile(fileURLToPath(new URL("../service-worker.js", import.meta.url)), "utf8");

test("Review request focuses Guardian on the selected pending request", async () => {
  let clickHandler;
  let navigatedTo = "";
  let focused = false;
  const client = {
    url: "http://127.0.0.1:8765/dashboard/",
    async navigate(url) { navigatedTo = url; return this; },
    async focus() { focused = true; }
  };
  const self = {
    location: new URL("http://127.0.0.1:8765/dashboard/service-worker.js"),
    addEventListener(name, handler) { if (name === "notificationclick") clickHandler = handler; },
    clients: {async matchAll() { return [client]; }, async openWindow() { throw new Error("Unexpected new window"); }}
  };
  vm.runInNewContext(script, {self, URL, encodeURIComponent});
  let completion;
  let closed = false;
  clickHandler({notification: {data: {requestId: "request-42"}, close() { closed = true; }},
    waitUntil(value) { completion = value; }});
  await completion;
  assert.equal(closed, true);
  assert.equal(new URL(navigatedTo).hash, "#request=request-42");
  assert.equal(focused, true);
});
