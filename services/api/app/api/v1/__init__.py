"""API v1 router registry."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    curriculum,
    parent,
    practice,
    progress,
    site,
    teacher,
    tutoring,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(curriculum.router)
api_router.include_router(practice.router)
api_router.include_router(progress.router)
api_router.include_router(tutoring.router)
api_router.include_router(site.router)
api_router.include_router(teacher.router)
api_router.include_router(parent.router)
api_router.include_router(admin.router)
api_router.include_router(ai.router)

__all__ = ["api_router"]
