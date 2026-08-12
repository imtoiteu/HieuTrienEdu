"""Authentication endpoints: register, login, refresh, profile."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import ParentProfile, StudentProfile, User, UserRole
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateProfileRequest,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# A real bcrypt hash of a value nobody can log in with, computed once at import. Verifying an
# incoming password against this when the account does not exist makes a "no such user" response
# cost the same as a "wrong password" one, so response timing does not reveal which emails are
# registered. A syntactically invalid placeholder would not work here — bcrypt rejects it
# immediately and returns far too fast.
_DUMMY_PASSWORD_HASH = hash_password("hietedu-timing-equaliser-not-a-real-password")


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    """Create a student or parent account. Teacher/admin accounts are created by an admin."""
    normalised_email = payload.email.strip().lower()

    existing = db.scalar(select(User).where(func.lower(User.email) == normalised_email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )

    user = User(
        email=normalised_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role,
        locale=payload.locale,
        phone=payload.phone,
        is_verified=False,
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.STUDENT:
        db.add(StudentProfile(user_id=user.id, grade=payload.grade or 6))
    elif payload.role == UserRole.PARENT:
        db.add(ParentProfile(user_id=user.id))

    db.commit()
    db.refresh(user)

    return AuthResponse(user=UserRead.model_validate(user), tokens=_issue_tokens(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().lower()))

    password_ok = verify_password(
        payload.password, user.password_hash if user else _DUMMY_PASSWORD_HASH
    )

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    user.last_login_at = dt.datetime.now(dt.UTC)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=UserRead.model_validate(user), tokens=_issue_tokens(user))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid refresh token: {exc}"
        ) from exc

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown account")

    return _issue_tokens(user)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
def update_me(payload: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> UserRead:
    for field in ("full_name", "locale", "phone", "avatar_url"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)

    if user.role == UserRole.STUDENT:
        profile = user.student_profile
        if profile is None:
            profile = StudentProfile(user_id=user.id, grade=6)
            db.add(profile)
            db.flush()
        if payload.grade is not None:
            profile.grade = payload.grade
        if payload.school is not None:
            profile.school = payload.school
        if payload.learning_goals is not None:
            profile.learning_goals = payload.learning_goals

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    user.password_hash = hash_password(payload.new_password)
    db.commit()
