from fastapi import APIRouter

from app.api.routes import campaigns, health, leads, ops, pipeline, telegram


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
