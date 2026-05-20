from app.models.workflow_log import WorkflowLog
from app.repositories.base import Repository


class WorkflowLogRepository(Repository):
    async def create_log(self, workflow_log: WorkflowLog) -> WorkflowLog:
        return await self.add(workflow_log)
