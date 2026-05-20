import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.operator_escalation import OperatorEscalation
from app.schemas.ops import (
    EscalationResolveRequest,
    FollowUpScheduleRequest,
    OutreachReviewAction,
)
from app.services.follow_up_service import FollowUpService
from app.services.operator_escalation_service import OperatorEscalationService
from app.services.ops_service import OpsService
from app.services.outreach_review_service import OutreachReviewService


router = APIRouter()


@router.get("/dashboard")
async def dashboard_snapshot(session: AsyncSession = Depends(get_db_session)) -> dict:
    return await OpsService(session).dashboard_snapshot()


@router.get("/metrics")
async def metrics(session: AsyncSession = Depends(get_db_session)) -> dict:
    return await OpsService(session).metrics()


@router.get("/outreach/review-queue")
async def review_queue(session: AsyncSession = Depends(get_db_session)) -> list[dict]:
    items = await OutreachReviewService(session).list_queue()
    return [
        {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "subject": item.subject,
            "body": item.body,
            "review_status": item.review_status.value,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.post("/outreach/{outreach_id}/approve")
async def approve_outreach(
    outreach_id: uuid.UUID,
    payload: OutreachReviewAction,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    outreach = await OutreachReviewService(session).approve(outreach_id, reviewer=payload.reviewer, notes=payload.notes)
    return {"id": str(outreach.id), "review_status": outreach.review_status.value, "status": outreach.status.value}


@router.post("/outreach/{outreach_id}/reject")
async def reject_outreach(
    outreach_id: uuid.UUID,
    payload: OutreachReviewAction,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    outreach = await OutreachReviewService(session).reject(outreach_id, reviewer=payload.reviewer, notes=payload.notes)
    return {"id": str(outreach.id), "review_status": outreach.review_status.value, "status": outreach.status.value}


@router.post("/outreach/{outreach_id}/edit")
async def edit_outreach(
    outreach_id: uuid.UUID,
    payload: OutreachReviewAction,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    outreach = await OutreachReviewService(session).edit(
        outreach_id,
        reviewer=payload.reviewer,
        subject=payload.subject,
        body=payload.body,
        notes=payload.notes,
    )
    return {"id": str(outreach.id), "review_status": outreach.review_status.value, "status": outreach.status.value}


@router.post("/outreach/{outreach_id}/follow-up")
async def schedule_follow_up(
    outreach_id: uuid.UUID,
    payload: FollowUpScheduleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    outreach = await FollowUpService(session).schedule(outreach_id, due_at=payload.due_at, actor=payload.actor)
    return {
        "id": str(outreach.id),
        "follow_up_status": outreach.follow_up_status.value,
        "follow_up_due_at": outreach.follow_up_due_at.isoformat() if outreach.follow_up_due_at else None,
    }


@router.post("/follow-ups/process-due")
async def process_due_followups(session: AsyncSession = Depends(get_db_session)) -> dict:
    items = await FollowUpService(session).process_due()
    return {"processed": len(items), "outreach_ids": [str(item.id) for item in items]}


@router.get("/escalations")
async def list_escalations(session: AsyncSession = Depends(get_db_session)) -> list[dict]:
    items = await OpsService(session).dashboard_snapshot()
    return items["escalations"]


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: uuid.UUID,
    payload: EscalationResolveRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    escalation = await session.get(OperatorEscalation, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    resolved = await OperatorEscalationService(session).resolve(
        escalation,
        actor=payload.actor,
        resolution_notes=payload.resolution_notes,
    )
    return {"id": str(resolved.id), "status": resolved.status.value}
