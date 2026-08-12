"""Shared test fixtures.

Every test runs against a fresh in-memory SQLite database with the real schema, so tests exercise
the actual models and constraints rather than mocks. The FastAPI dependency override swaps the
session factory, leaving application code untouched.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.security import hash_password
from app.main import app
from app.models import (
    Achievement,
    Base,
    Course,
    Question,
    ReviewStatus,
    Skill,
    SkillPrerequisite,
    StudentProfile,
    Subject,
    TeacherProfile,
    Topic,
    Unit,
    User,
    UserRole,
)

TEST_PASSWORD = "TestPass123!"


@pytest.fixture
def engine():
    # StaticPool keeps a single in-memory database across connections; without it each
    # connection would get its own empty database.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _fk_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine, db) -> Iterator[TestClient]:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------------------
# content fixtures
# --------------------------------------------------------------------------------------


@pytest.fixture
def curriculum(db: Session) -> dict:
    """A minimal but complete curriculum: two skills, one a prerequisite of the other."""
    subject = Subject(slug="mathematics", name="Mathematics", position=1)
    db.add(subject)
    db.flush()

    course = Course(subject_id=subject.id, slug="math-7", title="Mathematics — Grade 7", grade=7)
    db.add(course)
    db.flush()

    unit = Unit(course_id=course.id, slug="unit-fractions", title="Fractions")
    db.add(unit)
    db.flush()

    topic = Topic(unit_id=unit.id, slug="topic-fractions", title="Working with fractions")
    db.add(topic)
    db.flush()

    foundation = Skill(
        topic_id=topic.id, slug="equivalent-fractions", name="Equivalent fractions", difficulty=1
    )
    advanced = Skill(
        topic_id=topic.id, slug="adding-fractions", name="Adding fractions", difficulty=3
    )
    db.add_all([foundation, advanced])
    db.flush()

    db.add(SkillPrerequisite(skill_id=advanced.id, prerequisite_id=foundation.id, strength=1.0))

    for skill in (foundation, advanced):
        for index in range(3):
            db.add(
                Question(
                    slug=f"{skill.slug}-q{index}",
                    skill_id=skill.id,
                    subject_slug="mathematics",
                    grade=7,
                    topic_slug=topic.slug,
                    question_type="numeric",
                    difficulty=index + 1,
                    prompt="What is {{a}} + {{b}}?",
                    variables={
                        "a": {"type": "int", "min": 1, "max": 20},
                        "b": {"type": "int", "min": 1, "max": 20},
                    },
                    answer_spec={"expression": "a + b"},
                    hints=[{"text": "Add {{a}} and {{b}}."}],
                    solution=[{"text": "{{a}} + {{b}} = {{a+b}}."}],
                    status=ReviewStatus.PUBLISHED,
                    is_parametric=True,
                )
            )

    db.add(
        Achievement(
            slug="first-steps",
            name="First Steps",
            description="Answer your first question",
            criteria={"type": "questions_attempted", "value": 1},
            xp_reward=10,
        )
    )
    db.commit()

    return {
        "subject": subject,
        "course": course,
        "unit": unit,
        "topic": topic,
        "foundation": foundation,
        "advanced": advanced,
    }


# --------------------------------------------------------------------------------------
# user fixtures
# --------------------------------------------------------------------------------------


def _make_user(db: Session, email: str, role: UserRole, name: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
        full_name=name,
        role=role,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def student(db: Session) -> StudentProfile:
    user = _make_user(db, "student@example.com", UserRole.STUDENT, "Test Student")
    profile = StudentProfile(user_id=user.id, grade=7)
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture
def teacher(db: Session) -> TeacherProfile:
    user = _make_user(db, "teacher@example.com", UserRole.TEACHER, "Test Teacher")
    profile = TeacherProfile(user_id=user.id, subjects=["mathematics"], grades=[7])
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture
def admin(db: Session) -> User:
    user = _make_user(db, "admin@example.com", UserRole.ADMIN, "Test Admin")
    db.commit()
    return user


def auth_headers(client: TestClient, email: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


@pytest.fixture
def student_headers(client: TestClient, student: StudentProfile) -> dict[str, str]:
    return auth_headers(client, "student@example.com")


@pytest.fixture
def teacher_headers(client: TestClient, teacher: TeacherProfile) -> dict[str, str]:
    return auth_headers(client, "teacher@example.com")


@pytest.fixture
def admin_headers(client: TestClient, admin: User) -> dict[str, str]:
    return auth_headers(client, "admin@example.com")


@pytest.fixture
def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
