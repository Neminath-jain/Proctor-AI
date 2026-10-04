"""API v1 router configuration."""
from fastapi import APIRouter
from app.api.v1.endpoints import admin_exams, admin_ws, auth, candidate_exams, evidence, health, privacy

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(admin_exams.router)
api_router.include_router(admin_ws.router)
api_router.include_router(candidate_exams.router)
api_router.include_router(evidence.router)
api_router.include_router(privacy.router)

