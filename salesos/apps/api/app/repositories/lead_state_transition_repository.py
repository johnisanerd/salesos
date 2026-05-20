from app.models.lead_state_transition import LeadStateTransition
from app.repositories.base import Repository


class LeadStateTransitionRepository(Repository):
    async def create_transition(self, transition: LeadStateTransition) -> LeadStateTransition:
        return await self.add(transition)
