"""Own the approval event loop and its watchdog lifecycle."""
import asyncio
import threading
from .request_manager import ApprovalManager


class Broker:
    def __init__(self, config):
        self.config = config
        self.loop = asyncio.new_event_loop()
        self.manager = ApprovalManager(timeout=config.get("approval_timeout", 90),
                                       lease_seconds=config.get("lease_seconds", 120),
                                       capacity=config.get("capacity", 128))
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def set_timeout(self, seconds):
        """Change the deadline applied to newly-created requests."""
        self.manager.timeout = seconds
        self.config["approval_timeout"] = seconds

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.watchdog = self.loop.create_task(self._watch())
        self.loop.run_forever()
        self.watchdog.cancel()
        self.loop.run_until_complete(asyncio.gather(self.watchdog, return_exceptions=True))
        self.loop.close()

    async def _watch(self):
        while True:
            await asyncio.sleep(0.2)
            self.manager.sweep()

    def call(self, function, *args):
        async def execute():
            return function(*args)
        return asyncio.run_coroutine_threadsafe(execute(), self.loop).result(timeout=5)

    def wait(self, pending):
        return asyncio.run_coroutine_threadsafe(self.manager.wait(pending), self.loop)

    def close(self):
        self.call(self.manager.close)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)

