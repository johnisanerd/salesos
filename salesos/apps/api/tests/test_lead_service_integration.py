from __future__ import annotations

import asyncio
import unittest
import uuid

from sqlalchemy import text

from app.db.session import AsyncSessionFactory
from app.schemas.lead import LeadCreate
from app.services.lead_service import LeadService


class LeadServiceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_duplicate_submissions_do_not_corrupt_db(self) -> None:
        unique_name = f"Concurrent Lead {uuid.uuid4()}"
        payload = LeadCreate(
            business_name=unique_name,
            website="https://example.test",
            city="Austin",
            source="google_maps",
        )
        fingerprint = LeadService.build_fingerprint(payload)
        await self._cleanup_fingerprint(fingerprint)

        async def create_once():
            async with AsyncSessionFactory() as session:
                return await LeadService(session).create_or_get_lead(payload)

        try:
            first, second = await asyncio.gather(create_once(), create_once())
            lead_ids = {str(first[0].id), str(second[0].id)}
            created_flags = sorted([first[1], second[1]])

            self.assertEqual(len(lead_ids), 1)
            self.assertEqual(created_flags, [False, True])

            async with AsyncSessionFactory() as session:
                counts = await session.execute(
                    text(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM leads WHERE normalized_fingerprint = :fingerprint) AS lead_count,
                            (SELECT COUNT(*) FROM lead_state_transitions WHERE lead_id = :lead_id) AS transition_count,
                            (SELECT COUNT(*) FROM workflow_logs WHERE lead_id = :lead_id AND workflow_name = 'lead_ingestion') AS log_count
                        """
                    ),
                    {"fingerprint": fingerprint, "lead_id": str(first[0].id)},
                )
                row = counts.one()

            self.assertEqual(row.lead_count, 1)
            self.assertEqual(row.transition_count, 1)
            self.assertEqual(row.log_count, 1)
        finally:
            await self._cleanup_fingerprint(fingerprint)

    async def _cleanup_fingerprint(self, fingerprint: str) -> None:
        async with AsyncSessionFactory() as session:
            lead_id_result = await session.execute(
                text("SELECT id FROM leads WHERE normalized_fingerprint = :fingerprint"),
                {"fingerprint": fingerprint},
            )
            lead_ids = [str(item) for item in lead_id_result.scalars().all()]
            for lead_id in lead_ids:
                await session.execute(text("DELETE FROM workflow_logs WHERE lead_id = :lead_id"), {"lead_id": lead_id})
                await session.execute(
                    text("DELETE FROM lead_state_transitions WHERE lead_id = :lead_id"),
                    {"lead_id": lead_id},
                )
                await session.execute(text("DELETE FROM leads WHERE id = :lead_id"), {"lead_id": lead_id})
            await session.commit()


if __name__ == "__main__":
    unittest.main()
