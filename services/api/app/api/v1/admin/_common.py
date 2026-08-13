"""Shared building blocks for the admin API.

Three things live here because every admin module needs them and they must behave identically
everywhere: how a list endpoint paginates, how a state change is recorded in the audit trail, and
how a record is snapshotted before it is overwritten or deleted.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession
from app.models import AuditLog, ContentRevision, User, UserRole
from app.services.notifications import notify_admins, notify_user

T = TypeVar("T")

MAX_PAGE_SIZE = 200


# --------------------------------------------------------------------------------------
# authorisation
# --------------------------------------------------------------------------------------


def require_admin(user: CurrentUser) -> User:
    """Admin-only guard that also *returns* the acting user.

    ``require_roles`` is used as a router-level dependency and discards its result, which is fine
    for a pure gate but useless for the audit trail — every write here has to record who did it.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an administrator account",
        )
    return user


def require_staff(user: CurrentUser) -> User:
    """Admin or teacher. Used by read endpoints teachers legitimately need."""
    if user.role not in {UserRole.ADMIN, UserRole.TEACHER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a teacher or administrator account",
        )
    return user


CurrentAdmin = Annotated[User, Depends(require_admin)]
CurrentStaff = Annotated[User, Depends(require_staff)]


# --------------------------------------------------------------------------------------
# pagination
# --------------------------------------------------------------------------------------


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 25
    search: str | None = None
    sort: str | None = None
    order: str = "desc"


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> PageParams:
    return PageParams(page=page, page_size=page_size, search=search, sort=sort, order=order)


Pagination = Annotated[PageParams, Depends(page_params)]


class Page(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    pages: int = 0


def paginate(db: Session, query: Select, params: PageParams) -> tuple[list[Any], int]:
    """Run ``query`` for one page and return ``(rows, total)``.

    The count is taken from a subquery of the *unpaginated* statement with its ORDER BY stripped:
    ordering is meaningless inside COUNT and PostgreSQL rejects an ORDER BY over a column that is
    not in the select list of an aggregate subquery.
    """
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(count_query) or 0

    offset = (params.page - 1) * params.page_size
    rows = list(db.scalars(query.offset(offset).limit(params.page_size)).unique())
    return rows, total


def build_page(rows: list[Any], total: int, params: PageParams) -> dict[str, Any]:
    return {
        "items": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if params.page_size else 0,
    }


def apply_sort(query: Select, model: Any, params: PageParams, allowed: dict[str, Any]):
    """Order ``query`` by a whitelisted column.

    The whitelist is the point: interpolating a client-supplied column name into ``order_by`` is
    an injection vector, and an unknown name should fall back to a sensible default rather than
    500.
    """
    column = allowed.get(params.sort or "")
    if column is None:
        column = allowed.get("_default") or model.id
    return query.order_by(column.desc() if params.order == "desc" else column.asc())


# --------------------------------------------------------------------------------------
# audit trail
# --------------------------------------------------------------------------------------


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one row to the audit trail. Caller commits."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:400],
        changes=changes or {},
    )
    db.add(entry)
    return entry


def diff_fields(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compact ``{field: {"from": x, "to": y}}`` of what actually changed."""
    changes: dict[str, Any] = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value != new_value:
            changes[key] = {"from": _jsonable(old_value), "to": _jsonable(new_value)}
    return changes


def _jsonable(value: Any) -> Any:
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, list | dict | str | int | float | bool) or value is None:
        return value
    return str(value)


# --------------------------------------------------------------------------------------
# revisions
# --------------------------------------------------------------------------------------


def snapshot(
    db: Session,
    entity_type: str,
    entity_id: int,
    data: dict[str, Any],
    author: User | None = None,
    note: str | None = None,
) -> ContentRevision:
    """Store a restorable copy of a record before it is changed. Caller commits."""
    latest = db.scalar(
        select(func.max(ContentRevision.version)).where(
            ContentRevision.entity_type == entity_type,
            ContentRevision.entity_id == entity_id,
        )
    )
    revision = ContentRevision(
        entity_type=entity_type,
        entity_id=entity_id,
        version=(latest or 0) + 1,
        snapshot={key: _jsonable(value) for key, value in data.items()},
        note=note,
        author_id=author.id if author else None,
    )
    db.add(revision)
    return revision


# --------------------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------------------


def get_or_404(db: Session, model: Any, entity_id: int, label: str) -> Any:
    instance = db.get(model, entity_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found"
        )
    return instance


def next_position(db: Session, model: Any, *conditions) -> int:
    """Position value that puts a new row at the end of its list."""
    query = select(func.max(model.position))
    if conditions:
        query = query.where(*conditions)
    return (db.scalar(query) or 0) + 1


__all__ = [
    "CurrentAdmin",
    "CurrentStaff",
    "DbSession",
    "MAX_PAGE_SIZE",
    "Page",
    "PageParams",
    "Pagination",
    "apply_sort",
    "build_page",
    "diff_fields",
    "get_or_404",
    "next_position",
    "notify_admins",
    "notify_user",
    "paginate",
    "record_audit",
    "require_admin",
    "snapshot",
]
