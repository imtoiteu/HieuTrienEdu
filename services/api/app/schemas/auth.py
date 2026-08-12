"""Authentication and profile schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole

MIN_PASSWORD_LENGTH = 8


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=72)
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.STUDENT
    grade: int | None = Field(default=None, ge=1, le=12)
    locale: str = Field(default="en", max_length=8)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        # bcrypt silently ignores bytes past 72; reject rather than truncate so two different
        # long passwords can never become interchangeable.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes)")
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters with numbers or symbols")
        return value

    @field_validator("role")
    @classmethod
    def public_roles_only(cls, value: UserRole) -> UserRole:
        # Self-service signup may only create students and parents. Teachers and admins are
        # created by an admin — otherwise anyone could grant themselves teacher access.
        if value not in {UserRole.STUDENT, UserRole.PARENT}:
            raise ValueError("Only student and parent accounts can self-register")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class StudentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grade: int
    school: str | None = None
    xp_total: int
    level: int
    streak_days: int
    longest_streak_days: int
    last_activity_date: dt.date | None = None
    learning_goals: list[str] = Field(default_factory=list)


class TeacherProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    headline: str | None = None
    bio: str | None = None
    subjects: list[str] = Field(default_factory=list)
    grades: list[int] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    years_experience: int = 0
    languages: list[str] = Field(default_factory=list)
    rating: float = 0.0
    rating_count: int = 0
    is_featured: bool = False
    accepts_one_to_one: bool = True
    hourly_rate_vnd: int | None = None


class ParentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_preference: str = "email"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    locale: str
    avatar_url: str | None = None
    phone: str | None = None
    is_active: bool
    is_verified: bool
    created_at: dt.datetime

    student_profile: StudentProfileRead | None = None
    teacher_profile: TeacherProfileRead | None = None
    parent_profile: ParentProfileRead | None = None


class AuthResponse(BaseModel):
    user: UserRead
    tokens: TokenPair


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    locale: str | None = Field(default=None, max_length=8)
    phone: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=500)
    grade: int | None = Field(default=None, ge=1, le=12)
    school: str | None = Field(default=None, max_length=200)
    learning_goals: list[str] | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=72)
