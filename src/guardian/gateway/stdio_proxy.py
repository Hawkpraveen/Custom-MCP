"""Concurrent newline-delimited MCP relay for Claude Desktop."""
import asyncio
import concurrent.futures
import contextlib
import json
import logging
import sys
import threading
import uuid

from ..client import api
from ..config import MAX_APPROVAL_TIMEOUT
from ..protocol import MAX_MESSAGE_BYTES, encode, error, parse_message, request_key, requires_approval

log = logging.getLogger("guardian.stdio")


async def proxy(config, command, server_name):
    if not command:
        raise ValueError("An upstream executable is required after --")
    child = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE,
                                                limit=MAX_MESSAGE_BYTES + 1)
    scope = "stdio:" + str(uuid.uuid4())
    active = {}
    forwarded = set()
    write_lock = asyncio.Lock()
    output_lock = asyncio.Lock()
    incoming = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()

    def stdin_reader():
        try:
            while True:
                line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 2)
                asyncio.run_coroutine_threadsafe(incoming.put(line), loop).result()
                if not line or len(line) > MAX_MESSAGE_BYTES:
                    break
        except (RuntimeError, concurrent.futures.CancelledError):
            pass

    # A daemon reader avoids an uncancellable default-executor stdin read on Windows.
    threading.Thread(target=stdin_reader, daemon=True).start()

    async def output(message):
        async with output_lock:
            sys.stdout.buffer.write(encode(message))
            sys.stdout.buffer.flush()

    async def forward(message):
        async with write_lock:
            child.stdin.write(encode(message))
            await child.stdin.drain()

    async def cancel_at_broker(rpc_id):
        with contextlib.suppress(Exception):
            await asyncio.to_thread(api, config["broker_url"], "/api/cancel", config["producer_token"],
                                    {"scope": scope, "request_id": rpc_id}, 3)

    async def gate(message):
        key = request_key(message)
        try:
            result = await asyncio.to_thread(api, config["broker_url"], "/api/authorize", config["producer_token"],
                                            {"server": server_name, "source": "Claude Desktop / stdio",
                                             "scope": scope, "message": message}, MAX_APPROVAL_TIMEOUT + 10)
            if result.get("allowed") is True:
                forwarded.add(key)
                await forward(message)
            else:
                await output(error(message["id"], "Request blocked by Guardian: " + str(result.get("state", "denied"))))
                active.pop(key, None)
        except asyncio.CancelledError:
            raise
        except Exception:
            await output(error(message["id"], "Authorization unavailable; request blocked"))
            active.pop(key, None)

    async def read_client():
        while True:
            line = await incoming.get()
            if not line:
                return
            try:
                message = parse_message(line)
            except (ValueError, UnicodeError):
                await output(error(None, "Invalid MCP message", -32600))
                if len(line) > MAX_MESSAGE_BYTES:
                    return
                continue
            if message.get("method") == "notifications/cancelled":
                rpc_id = message.get("params", {}).get("requestId")
                key = json.dumps(rpc_id, ensure_ascii=True)
                entry = active.get(key)
                if entry and key not in forwarded:
                    entry[0].cancel()
                    await cancel_at_broker(rpc_id)
                    active.pop(key, None)
                    continue
            if requires_approval(message):
                key = request_key(message)
                if key in active:
                    await output(error(message["id"], "Duplicate in-flight request ID"))
                elif len(active) >= 128:
                    await output(error(message["id"], "Gateway capacity exceeded"))
                else:
                    active[key] = (asyncio.create_task(gate(message)), message["id"])
            else:
                await forward(message)

    async def read_upstream():
        while True:
            line = await child.stdout.readline()
            if not line:
                return
            message = parse_message(line)
            if "method" not in message:
                key = request_key(message)
                forwarded.discard(key)
                active.pop(key, None)
            await output(message)

    async def drain_stderr():
        # Drain so an upstream cannot deadlock; do not copy unknown secrets to logs.
        while await child.stderr.read(16384):
            pass

    readers = [asyncio.create_task(read_client()), asyncio.create_task(read_upstream())]
    stderr_task = asyncio.create_task(drain_stderr())
    try:
        done, _ = await asyncio.wait(readers, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        pending = list(active.values())
        for task, _ in pending:
            task.cancel()
        await asyncio.gather(*(cancel_at_broker(rpc_id) for _, rpc_id in pending), return_exceptions=True)
        await asyncio.gather(*(task for task, _ in pending), return_exceptions=True)
        for task in readers + [stderr_task]:
            task.cancel()
        await asyncio.gather(*readers, stderr_task, return_exceptions=True)
        if child.stdin:
            child.stdin.close()
        try:
            await asyncio.wait_for(child.wait(), 2)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                child.terminate()
            await child.wait()

