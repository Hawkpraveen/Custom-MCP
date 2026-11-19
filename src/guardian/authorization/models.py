"""Immutable request snapshot and pending approval record."""
import asyncio
from dataclasses import dataclass, field


@dataclass
class Pending:
    id: str
    server: str
    source: str
    scope: str
    message: dict
    fingerprint: str
    created: float
    deadline: float
    expires_at: float
    future: asyncio.Future = field(repr=False)
    state: str = "pending"

    def public(self):
        return {"id": self.id, "server": self.server, "source": self.source,
                "message": self.message, "fingerprint": self.fingerprint,
                "created": self.created, "deadline": self.deadline, "state": self.state}

