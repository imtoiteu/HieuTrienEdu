"""Shared FastAPI dependencies: current user resolution and role guards."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token
from app.models import ParentProfile, StudentProfile, TeacherProfile, User, UserRole

# auto_error=False so we can return our own 401 shape rather than FastAPI's terse default.
bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_EXCEPTION

    try:
        payload = decode_token(credentials.credentials, "access")
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
            selectinload(User.parent_profile),
        )
    )
    if user is None:
        raise CREDENTIALS_EXCEPTION
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Resolve the caller if a valid token is present, otherwise ``None``.

    Used by endpoints that serve everyone but personalise for signed-in students — a lesson page
    is public, yet a logged-in student should see their own progress on it.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        # A malformed or expired token on a public endpoint means "anonymous", not "error".
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DbSession = Annotated[Session, Depends(get_db)]


def require_roles(*roles: UserRole):
    """Dependency factory guarding an endpoint behind one or more roles.

    Admins are intentionally allowed everywhere — an admin locked out of the teacher tools would
    be unable to support teachers, which is the opposite of useful.
    """
    allowed: set[str] = {str(role) for role in roles}

    def guard(user: CurrentUser) -> User:
        if user.role == UserRole.ADMIN or user.role in allowed:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires one of these roles: {', '.join(sorted(allowed))}",
        )

    return guard


def get_current_student(user: CurrentUser, db: DbSession) -> StudentProfile:
    """Resolve the acting student profile, creating one for a student user that lacks it."""
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This action requires a student account"
        )
    profile = user.student_profile
    if profile is None:
        profile = StudentProfile(user_id=user.id, grade=6)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_current_teacher(user: CurrentUser, db: DbSession) -> TeacherProfile:
    if user.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This action requires a teacher account"
        )
    profile = user.teacher_profile
    if profile is None:
        profile = TeacherProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_current_parent(user: CurrentUser, db: DbSession) -> ParentProfile:
    if user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This action requires a parent account"
        )
    profile = user.parent_profile
    if profile is None:
        profile = ParentProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


CurrentStudent = Annotated[StudentProfile, Depends(get_current_student)]
CurrentTeacher = Annotated[TeacherProfile, Depends(get_current_teacher)]
CurrentParent = Annotated[ParentProfile, Depends(get_current_parent)]


def assert_can_view_student(user: User, student: StudentProfile,
                            linked_student_ids: Iterable[int] | None = None) -> None:
    """Authorise access to one student's data.

    Called from every endpoint that returns student-identifying information. Teachers and admins
    see all students; a parent sees only their linked children; a student sees only themselves.
    """
    if user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        return
    if user.role == UserRole.STUDENT and user.student_profile \
            and user.student_profile.id == student.id:
        return
    if user.role == UserRole.PARENT and linked_student_ids is not None \
            and student.id in set(linked_student_ids):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this student's data",
    )
