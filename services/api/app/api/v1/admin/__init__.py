"""Admin API.

Split into one module per area of the back office rather than a single file, because the admin
surface is the largest part of the API and a 4,000-line module is unreviewable. Every sub-router
is mounted under ``/admin`` and guards itself with the ``CurrentAdmin`` dependency — the guard is
per-endpoint rather than router-level so each handler also *has* the acting user for the audit
trail.
"""

from fastapi import APIRouter

from app.api.v1.admin import (
    categories,
    classes,
    cms,
    curriculum,
    dashboard,
    enrollments,
    leads,
    lessons,
    media,
    notifications,
    questions,
    students,
    teachers,
)

router = APIRouter(prefix="/admin")

router.include_router(dashboard.router, tags=["admin"])
router.include_router(categories.router)
router.include_router(curriculum.router)
router.include_router(lessons.router)
router.include_router(questions.router)
router.include_router(students.router)
router.include_router(teachers.router)
router.include_router(leads.router)
router.include_router(enrollments.router)
router.include_router(enrollments.orders_router)
router.include_router(classes.router)
router.include_router(classes.sessions_router)
router.include_router(media.router)
router.include_router(cms.router)
router.include_router(cms.programs_router)
router.include_router(notifications.router)

__all__ = ["router"]
