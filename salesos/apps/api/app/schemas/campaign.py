import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CampaignStatus


class CampaignRead(BaseModel):
    id: uuid.UUID
    name: str
    status: CampaignStatus
    created_at: datetime

    model_config = {"from_attributes": True}
