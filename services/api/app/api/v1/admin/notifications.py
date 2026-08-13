"""Notification centre and the audit-log viewer."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    build_page,
    get_or_404,
    paginate,
)
from app.core.deps import CurrentUser
from app.models import AuditLog, Notification, User, UserRole

router = APIRouter(tags=["admin:notifications"])


def _row(item: Notification) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "body": item.body,
        "link_url": item.link_url,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "is_read": item.is_read,
        "read_at": item.read_at,
        "created_at": item.created_at,
    }


def _visible_to(user: User):
    """Notifications addressed to this user personally, or broadcast to their role.

    A broadcast row has ``user_id IS NULL`` and an ``audience_role``; that is how a consultation
    request reaches every administrator instead of whichever one happened to be created first.
    """
    return or_(
        Notification.user_id == user.id,
        Notification.audience_role == user.role,
    )


@router.get("/notifications")
def list_notifications(
    db: DbSession,
    user: CurrentUser,
    unread_only: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    """A signed-in user's notifications.

    Deliberately not admin-only: teachers receive course-assignment notices and students receive
    enrollment updates through the same table, and giving each role its own endpoint would be
    three copies of this query.
    """
    query = select(Notification).where(_visible_to(user))
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(Notification.created_at.desc())
    rows, total = paginate(db, query, params)

    unread = len(
        db.execute(
            select(Notification.id).where(_visible_to(user), Notification.is_read.is_(False))
        ).all()
    )
    result = build_page([_row(row) for row in rows], total, params)
    result["unread"] = unread
    return result


@router.get("/notifications/unread-count")
def unread_count(db: DbSession, user: CurrentUser) -> dict[str, int]:
    rows = db.execute(
        select(Notification.id).where(_visible_to(user), Notification.is_read.is_(False))
    ).all()
    return {"unread": len(rows)}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    notification = get_or_404(db, Notification, notification_id, "Notification")
    # Only touch rows this user can actually see.
    if notification.user_id not in (None, user.id) or (
        notification.user_id is None and notification.audience_role != user.role
    ):
        return {"id": notification_id, "is_read": notification.is_read}
    notification.is_read = True
    notification.read_at = dt.datetime.now(dt.UTC)
    db.commit()
    return {"id": notification.id, "is_read": True}


@router.post("/notifications/read-all")
def mark_all_read(db: DbSession, user: CurrentUser) -> dict[str, int]:
    rows = list(
        db.scalars(
            select(Notification).where(_visible_to(user), Notification.is_read.is_(False))
        )
    )
    now = dt.datetime.now(dt.UTC)
    for notification in rows:
        notification.is_read = True
        notification.read_at = now
    db.commit()
    return {"marked": len(rows)}


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: int, db: DbSession, user: CurrentUser) -> None:
    notification = get_or_404(db, Notification, notification_id, "Notification")
    if notification.user_id == user.id or user.role == UserRole.ADMIN:
        db.delete(notification)
        db.commit()


# --------------------------------------------------------------------------------------
# audit log
# --------------------------------------------------------------------------------------


@router.get("/audit-log")
def list_audit(
    db: DbSession,
    admin: CurrentAdmin,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
    entity_id: Annotated[int | None, Query()] = None,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if action:
        query = query.where(AuditLog.action == action)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(AuditLog.summary.ilike(pattern), AuditLog.actor_email.ilike(pattern))
        )

    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(AuditLog.created_at.desc())
    rows, total = paginate(db, query, params)
    items = [
        {
            "id": entry.id,
            "actor_id": entry.actor_id,
            "actor_email": entry.actor_email,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "summary": entry.summary,
            "changes": entry.changes or {},
            "created_at": entry.created_at,
        }
        for entry in rows
    ]
    return build_page(items, total, params)


@router.get("/staff")
def list_staff(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    """Assignable staff, for the "assign to" pickers on enquiries and classes."""
    rows = db.scalars(
        select(User)
        .where(User.role.in_([UserRole.ADMIN, UserRole.TEACHER]), User.is_active.is_(True))
        .options(selectinload(User.teacher_profile))
        .order_by(User.full_name)
    ).unique()
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "teacher_id": user.teacher_profile.id if user.teacher_profile else None,
        }
        for user in rows
    ]
