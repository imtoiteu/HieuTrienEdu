"""Raising notifications.

A service rather than a helper inside the admin API package, because the *public* endpoints are
what raise most of them — a consultation form submitted by an anonymous visitor is exactly the
event an administrator needs to hear about. Having the public router import from the admin router
would be a layering inversion; both importing this is not.

Every function adds to the session and leaves committing to the caller, so a notification is
written in the same transaction as the thing that caused it. A lead that fails to save cannot
leave a phantom notification behind.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Notification, NotificationKind, UserRole

__all__ = ["notify_admins", "notify_user"]


def notify_admins(
    db: Session,
    kind: NotificationKind | str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    """Raise a notification addressed to every administrator.

    Broadcast (``user_id = NULL`` plus an ``audience_role``) rather than fanned out to one row per
    admin: a new enquiry is not addressed to a particular person, and creating N rows would mean
    one administrator reading it leaves it unread for everyone else.
    """
    notification = Notification(
        user_id=None,
        audience_role=UserRole.ADMIN,
        kind=str(kind),
        title=title[:250],
        body=body,
        link_url=link_url,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    return notification


def notify_user(
    db: Session,
    user_id: int,
    kind: NotificationKind | str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    """Raise a notification for one specific person."""
    notification = Notification(
        user_id=user_id,
        audience_role=None,
        kind=str(kind),
        title=title[:250],
        body=body,
        link_url=link_url,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    return notification
