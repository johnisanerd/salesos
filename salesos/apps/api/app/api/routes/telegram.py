from fastapi import APIRouter

from app.schemas.telegram import TelegramAlertRequest
from app.services.telegram_service import TelegramAlertService


router = APIRouter()


@router.post("/alerts")
async def send_alert(payload: TelegramAlertRequest) -> dict:
    return await TelegramAlertService().send_alert(
        title=payload.title,
        message=payload.message,
        level=payload.level,
        metadata=payload.metadata,
    )
