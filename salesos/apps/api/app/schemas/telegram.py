from typing import Any

from pydantic import BaseModel, Field


class TelegramAlertRequest(BaseModel):
    title: str
    message: str
    level: str = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)
