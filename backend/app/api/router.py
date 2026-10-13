"""API v1 router configuration."""

from fastapi import APIRouter
from app.api.v1.endpoints import audit, claims, comparisons, health, policies, qa, rules

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(policies.router)
api_router.include_router(rules.router)
api_router.include_router(qa.router)
api_router.include_router(claims.router)
api_router.include_router(comparisons.router)
api_router.include_router(audit.router)
