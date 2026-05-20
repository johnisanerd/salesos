from __future__ import annotations

import asyncio
import unittest
import uuid
from datetime import UTC, datetime

from app.models.enums import LeadState, LeadStatus
from app.models.lead import Lead
from app.services.lead_lifecycle_service import LeadLifecycleService


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _: object) -> None:
        self.refreshes += 1


class LeadLifecycleServiceTests(unittest.TestCase):
    def test_transition_is_idempotent(self) -> None:
        async def run_test() -> None:
            session = FakeSession()
            service = LeadLifecycleService(session)  # type: ignore[arg-type]
            lead = Lead(
                id=uuid.uuid4(),
                business_name="Northwind Growth Studio",
                source="google_maps",
                status=LeadStatus.new,
                lifecycle_state=LeadState.DISCOVERED,
                state_updated_at=datetime.now(UTC),
                state_timestamps={LeadState.DISCOVERED.value: datetime.now(UTC).isoformat()},
                normalized_fingerprint="fingerprint",
                metadata_json={},
            )

            changed = await service.transition(lead, LeadState.ENRICHED)
            skipped = await service.transition(lead, LeadState.ENRICHED)

            self.assertTrue(changed)
            self.assertFalse(skipped)
            self.assertEqual(lead.lifecycle_state, LeadState.ENRICHED)
            self.assertEqual(len(session.added), 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
