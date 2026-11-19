import asyncio
import unittest

from support import call
from guardian.authorization.request_manager import ApprovalManager


class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    def manager(self, **kwargs):
        manager = ApprovalManager(**kwargs)
        manager.heartbeat("ui")
        self.addCleanup(manager.close)
        return manager

    async def test_snapshot_cannot_be_mutated_by_caller(self):
        manager = self.manager()
        message = call()
        pending = manager.create("server", "client", "scope", message)
        message["params"]["arguments"]["note"] = "changed"
        self.assertEqual(pending.message["params"]["arguments"]["note"], "test")

    async def test_independent_decisions_out_of_order(self):
        manager = self.manager()
        first = manager.create("s", "c", "scope", call(1))
        second = manager.create("s", "c", "scope", call(2))
        manager.decide(second.id, second.fingerprint, True, "ui")
        manager.decide(first.id, first.fingerprint, False, "ui")
        self.assertEqual(await manager.wait(first), "denied")
        self.assertEqual(await manager.wait(second), "approved")

    async def test_approval_is_single_use(self):
        manager = self.manager()
        pending = manager.create("s", "c", "scope", call())
        manager.decide(pending.id, pending.fingerprint, True, "ui")
        with self.assertRaises(ValueError):
            manager.decide(pending.id, pending.fingerprint, True, "ui")

    async def test_timeout_rejects_late_approval(self):
        manager = self.manager(timeout=0.02)
        pending = manager.create("s", "c", "scope", call())
        self.assertEqual(await manager.wait(pending), "expired")
        with self.assertRaises(ValueError):
            manager.decide(pending.id, pending.fingerprint, True, "ui")

    async def test_offline_and_shutdown_fail_closed(self):
        manager = self.manager()
        pending = manager.create("s", "c", "scope", call())
        manager.disconnect("ui")
        self.assertEqual(await manager.wait(pending), "offline")
        with self.assertRaises(ValueError):
            manager.create("s", "c", "scope", call())

    async def test_lease_expiry_rejects_decision(self):
        manager = self.manager(lease_seconds=0.01)
        pending = manager.create("s", "c", "scope", call())
        await asyncio.sleep(0.02)
        with self.assertRaises(ValueError):
            manager.decide(pending.id, pending.fingerprint, True, "ui")
        self.assertEqual(await manager.wait(pending), "offline")

    async def test_wrong_fingerprint_and_wrong_approver(self):
        manager = self.manager()
        pending = manager.create("s", "c", "scope", call())
        for digest, instance in [("wrong", "ui"), (pending.fingerprint, "other")]:
            with self.assertRaises(ValueError):
                manager.decide(pending.id, digest, True, instance)
        self.assertFalse(pending.future.done())

    async def test_cancellation_is_scoped_and_ids_keep_their_type(self):
        manager = self.manager()
        first = manager.create("s", "c", "a", call(1))
        second = manager.create("s", "c", "b", call(1))
        third = manager.create("s", "c", "a", call("1"))
        manager.cancel("a", 1)
        self.assertEqual(await manager.wait(first), "cancelled")
        self.assertFalse(second.future.done())
        self.assertFalse(third.future.done())

    async def test_duplicate_and_capacity_are_rejected(self):
        manager = self.manager(capacity=1)
        manager.create("s", "c", "a", call(1))
        with self.assertRaises(ValueError):
            manager.create("s", "c", "a", call(1))
        with self.assertRaises(ValueError):
            manager.create("s", "c", "a", call(2))

    async def test_new_heartbeat_cannot_revive_old_pending_requests(self):
        manager = self.manager(lease_seconds=5)
        pending = manager.create("s", "c", "a", call())
        manager.last_seen -= 10  # Expire the old lease without a scheduler-sensitive 10 ms window.
        manager.heartbeat("replacement-ui")
        self.assertEqual(await manager.wait(pending), "offline")
        self.assertTrue(manager.available)

    async def test_shutdown_resolves_pending_requests(self):
        manager = self.manager()
        pending = manager.create("s", "c", "a", call())
        manager.close()
        self.assertEqual(await manager.wait(pending), "offline")

