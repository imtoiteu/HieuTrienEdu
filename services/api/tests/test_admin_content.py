"""Admin content management: taxonomy, courses, lesson authoring and the question bank.

These assert on *behaviour*, not status codes: that a published lesson is the one students read,
that an unpublished draft is not, that deleting a course really removes its lessons, and that a
question the engine cannot render is refused before it reaches a student.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ContentCategory,
    Course,
    Lesson,
    Question,
    ReviewStatus,
    Skill,
    Topic,
    Unit,
)

API = "/api/v1/admin"


# --------------------------------------------------------------------------------------
# taxonomy
# --------------------------------------------------------------------------------------


def test_category_crud_and_vietnamese_slug(client: TestClient, admin_headers, db: Session):
    response = client.post(
        f"{API}/categories",
        headers=admin_headers,
        json={"name": "Luyện thi vào 10", "kind": "program"},
    )
    assert response.status_code == 201, response.text
    created = response.json()

    # Vietnamese must transliterate rather than collapse into hyphens.
    assert created["slug"] == "luyen-thi-vao-10"

    child = client.post(
        f"{API}/categories",
        headers=admin_headers,
        json={"name": "Toán vào 10", "kind": "topic", "parent_id": created["id"]},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == created["id"]

    tree = client.get(f"{API}/categories/tree", headers=admin_headers).json()
    root = next(node for node in tree if node["id"] == created["id"])
    assert [c["id"] for c in root["children"]] == [child.json()["id"]]

    # Unpublishing hides it from the public endpoint but keeps the row.
    client.post(f"{API}/categories/{created['id']}/unpublish", headers=admin_headers)
    public = client.get("/api/v1/site/categories").json()
    assert all(node["id"] != created["id"] for node in public)
    assert db.get(ContentCategory, created["id"]) is not None

    client.post(f"{API}/categories/{created['id']}/publish", headers=admin_headers)
    public = client.get("/api/v1/site/categories").json()
    assert any(node["id"] == created["id"] for node in public)


def test_category_cycle_is_rejected(client: TestClient, admin_headers):
    a = client.post(
        f"{API}/categories", headers=admin_headers, json={"name": "Parent"}
    ).json()
    b = client.post(
        f"{API}/categories",
        headers=admin_headers,
        json={"name": "Child", "parent_id": a["id"]},
    ).json()

    # Making the parent a child of its own child would make the tree infinite.
    response = client.patch(
        f"{API}/categories/{a['id']}", headers=admin_headers, json={"parent_id": b["id"]}
    )
    assert response.status_code == 400
    assert "loop" in response.json()["detail"].lower()


def test_deleting_category_reparents_children(client: TestClient, admin_headers, db: Session):
    parent = client.post(
        f"{API}/categories", headers=admin_headers, json={"name": "Group"}
    ).json()
    child = client.post(
        f"{API}/categories",
        headers=admin_headers,
        json={"name": "Nested", "parent_id": parent["id"]},
    ).json()

    deleted = client.delete(f"{API}/categories/{parent['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    db.expire_all()
    surviving = db.get(ContentCategory, child["id"])
    assert surviving is not None, "children must survive their parent being deleted"
    assert surviving.parent_id is None


# --------------------------------------------------------------------------------------
# courses
# --------------------------------------------------------------------------------------


def test_course_publish_controls_public_visibility(
    client: TestClient, admin_headers, curriculum, db: Session
):
    subject_id = curriculum["subject"].id
    created = client.post(
        f"{API}/courses",
        headers=admin_headers,
        json={"subject_id": subject_id, "title": "Toán lớp 9", "grade": 9, "status": "draft"},
    )
    assert created.status_code == 201, created.text
    course = created.json()
    assert course["is_published"] is False

    # A draft course must not appear in the public catalogue.
    public = client.get("/api/v1/curriculum/courses").json()
    assert all(row["slug"] != course["slug"] for row in public)

    published = client.post(
        f"{API}/courses/{course['id']}/status?status=published", headers=admin_headers
    )
    assert published.status_code == 200
    assert published.json()["is_published"] is True

    public = client.get("/api/v1/curriculum/courses").json()
    assert any(row["slug"] == course["slug"] for row in public)


def test_one_course_per_subject_and_grade(client: TestClient, admin_headers, curriculum):
    subject_id = curriculum["subject"].id
    # The fixture already has grade 7 for this subject.
    response = client.post(
        f"{API}/courses",
        headers=admin_headers,
        json={"subject_id": subject_id, "title": "Duplicate", "grade": 7},
    )
    assert response.status_code == 409
    assert "grade 7" in response.json()["detail"]


def test_duplicate_course_deep_copies_structure(
    client: TestClient, admin_headers, curriculum, db: Session
):
    course_id = curriculum["course"].id
    response = client.post(f"{API}/courses/{course_id}/duplicate", headers=admin_headers)
    assert response.status_code == 201, response.text
    clone = response.json()

    assert clone["status"] == "draft", "a duplicate must never go live automatically"
    assert clone["grade"] != curriculum["course"].grade

    original_units = db.scalars(select(Unit).where(Unit.course_id == course_id)).all()
    clone_units = db.scalars(select(Unit).where(Unit.course_id == clone["id"])).all()
    assert len(clone_units) == len(original_units) > 0

    # Skills are copied, questions are not — they are reusable content in their own right.
    clone_topics = db.scalars(
        select(Topic).where(Topic.unit_id.in_([u.id for u in clone_units]))
    ).all()
    clone_skills = db.scalars(
        select(Skill).where(Skill.topic_id.in_([t.id for t in clone_topics]))
    ).all()
    assert len(clone_skills) == 2
    assert db.scalars(
        select(Question).where(Question.skill_id.in_([s.id for s in clone_skills]))
    ).all() == []


def test_deleting_course_removes_its_lessons(
    client: TestClient, admin_headers, curriculum, db: Session
):
    topic_id = curriculum["topic"].id
    lesson = client.post(
        f"{API}/lessons",
        headers=admin_headers,
        json={
            "topic_id": topic_id,
            "title": "Doomed lesson",
            "blocks": [{"type": "text", "markdown": "hello"}],
        },
    ).json()

    assert client.delete(
        f"{API}/courses/{curriculum['course'].id}", headers=admin_headers
    ).status_code == 204

    db.expire_all()
    assert db.get(Lesson, lesson["id"]) is None
    assert db.get(Course, curriculum["course"].id) is None


def test_skill_with_questions_cannot_be_deleted(client: TestClient, admin_headers, curriculum):
    """Deleting would cascade the question bank and every student attempt away."""
    response = client.delete(
        f"{API}/skills/{curriculum['foundation'].id}", headers=admin_headers
    )
    assert response.status_code == 409
    assert "exercise" in response.json()["detail"].lower()


def test_structure_reorder_persists(client: TestClient, admin_headers, curriculum, db: Session):
    unit_id = curriculum["unit"].id
    second = client.post(
        f"{API}/topics", headers=admin_headers, json={"unit_id": unit_id, "title": "Second topic"}
    ).json()
    first_id = curriculum["topic"].id

    response = client.post(
        f"{API}/structure/topics/reorder",
        headers=admin_headers,
        json={"ids": [second["id"], first_id]},
    )
    assert response.status_code == 200

    db.expire_all()
    assert db.get(Topic, second["id"]).position == 1
    assert db.get(Topic, first_id).position == 2


# --------------------------------------------------------------------------------------
# lesson authoring
# --------------------------------------------------------------------------------------


def test_lesson_draft_is_invisible_until_published(
    client: TestClient, admin_headers, student_headers, curriculum, db: Session
):
    created = client.post(
        f"{API}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Phương trình bậc nhất",
            "blocks": [
                {"type": "heading", "text": "Lý thuyết"},
                {"type": "text", "markdown": "Nội dung"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    lesson = created.json()
    assert lesson["status"] == "draft"

    # The live body is empty while it is a draft, so a student reading it sees nothing.
    db.expire_all()
    assert db.get(Lesson, lesson["id"]).blocks == []
    assert len(db.get(Lesson, lesson["id"]).draft_blocks) == 2

    published = client.post(f"{API}/lessons/{lesson['id']}/publish", headers=admin_headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    db.expire_all()
    stored = db.get(Lesson, lesson["id"])
    assert len(stored.blocks) == 2
    assert stored.has_draft is False

    # And now a student can actually read it.
    student_view = client.get(
        f"/api/v1/curriculum/lessons/{lesson['slug']}", headers=student_headers
    )
    assert student_view.status_code == 200
    assert len(student_view.json()["blocks"]) == 2


def test_editing_published_lesson_does_not_change_what_students_read(
    client: TestClient, admin_headers, student_headers, curriculum, db: Session
):
    lesson = client.post(
        f"{API}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Live lesson",
            "status": "published",
            "blocks": [{"type": "text", "markdown": "Original text"}],
        },
    ).json()

    # Editing writes only to the draft.
    client.patch(
        f"{API}/lessons/{lesson['id']}",
        headers=admin_headers,
        json={"blocks": [{"type": "text", "markdown": "Work in progress"}]},
    )

    student_view = client.get(
        f"/api/v1/curriculum/lessons/{lesson['slug']}", headers=student_headers
    ).json()
    assert student_view["blocks"][0]["markdown"] == "Original text"

    client.post(f"{API}/lessons/{lesson['id']}/publish", headers=admin_headers)
    student_view = client.get(
        f"/api/v1/curriculum/lessons/{lesson['slug']}", headers=student_headers
    ).json()
    assert student_view["blocks"][0]["markdown"] == "Work in progress"


def test_lesson_block_validation_rejects_broken_content(
    client: TestClient, admin_headers, curriculum
):
    base = {"topic_id": curriculum["topic"].id, "title": "Bad blocks"}

    unknown = client.post(
        f"{API}/lessons", headers=admin_headers, json={**base, "blocks": [{"type": "nonsense"}]}
    )
    assert unknown.status_code == 422
    assert "Unknown block type" in unknown.json()["detail"]

    missing = client.post(
        f"{API}/lessons", headers=admin_headers, json={**base, "blocks": [{"type": "heading"}]}
    )
    assert missing.status_code == 422
    assert "missing" in missing.json()["detail"]

    # An assessment block pointing at nothing renders as a button that does nothing.
    empty_practice = client.post(
        f"{API}/lessons", headers=admin_headers, json={**base, "blocks": [{"type": "practice"}]}
    )
    assert empty_practice.status_code == 422
    assert "skill" in empty_practice.json()["detail"]


def test_lesson_revision_history_and_restore(client: TestClient, admin_headers, curriculum):
    lesson = client.post(
        f"{API}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Versioned",
            "status": "published",
            "blocks": [{"type": "text", "markdown": "Version one"}],
        },
    ).json()

    client.patch(
        f"{API}/lessons/{lesson['id']}",
        headers=admin_headers,
        json={"blocks": [{"type": "text", "markdown": "Version two"}]},
    )
    client.post(f"{API}/lessons/{lesson['id']}/publish", headers=admin_headers)

    revisions = client.get(f"{API}/lessons/{lesson['id']}/revisions", headers=admin_headers).json()
    assert len(revisions) == 1

    restored = client.post(
        f"{API}/lessons/{lesson['id']}/revisions/{revisions[0]['id']}/restore",
        headers=admin_headers,
    )
    assert restored.status_code == 200

    # Restoring loads into the draft so it can be reviewed before going live again.
    detail = client.get(f"{API}/lessons/{lesson['id']}", headers=admin_headers).json()
    assert detail["draft_blocks"][0]["markdown"] == "Version one"
    assert detail["blocks"][0]["markdown"] == "Version two"


def test_lesson_preview_matches_student_shape(client: TestClient, admin_headers, curriculum):
    lesson = client.post(
        f"{API}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Preview me",
            "blocks": [{"type": "summary", "points": ["One", "Two"], "section": "theory"}],
        },
    ).json()

    preview = client.get(f"{API}/lessons/{lesson['id']}/preview", headers=admin_headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["is_draft_preview"] is True
    assert body["blocks"][0]["points"] == ["One", "Two"]
    # Same field names as the public lesson endpoint, so one renderer serves both.
    for key in ("title", "summary", "objectives", "blocks", "topic_slug"):
        assert key in body


# --------------------------------------------------------------------------------------
# question bank
# --------------------------------------------------------------------------------------


def test_create_multiple_choice_and_preview_hides_answer(
    client: TestClient, admin_headers, curriculum
):
    created = client.post(
        f"{API}/questions",
        headers=admin_headers,
        json={
            "skill_id": curriculum["foundation"].id,
            "question_type": "multiple_choice",
            "prompt": "2 + 3 = ?",
            "options": {
                "choices": [
                    {"id": "a", "label": "4", "is_correct": False},
                    {"id": "b", "label": "5", "is_correct": True},
                ]
            },
            "answer_spec": {"choice_ids": ["b"]},
        },
    )
    assert created.status_code == 201, created.text
    question = created.json()

    revealed = client.get(
        f"{API}/questions/{question['id']}/preview", headers=admin_headers
    ).json()
    assert "answer" in revealed
    assert revealed["student_view"]["prompt"] == "2 + 3 = ?"

    as_student = client.get(
        f"{API}/questions/{question['id']}/preview?reveal=false", headers=admin_headers
    ).json()
    assert "answer" not in as_student, "preview-as-student must not leak the answer"
    assert "solution" not in as_student


def test_unanswerable_questions_are_refused(client: TestClient, admin_headers, curriculum):
    skill_id = curriculum["foundation"].id

    no_correct = client.post(
        f"{API}/questions",
        headers=admin_headers,
        json={
            "skill_id": skill_id,
            "question_type": "multiple_choice",
            "prompt": "Pick one",
            "options": {"choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}]},
        },
    )
    assert no_correct.status_code == 422
    assert "correct" in no_correct.json()["detail"].lower()

    one_option = client.post(
        f"{API}/questions",
        headers=admin_headers,
        json={
            "skill_id": skill_id,
            "question_type": "multiple_choice",
            "prompt": "Pick one",
            "options": {"choices": [{"id": "a", "label": "4", "is_correct": True}]},
        },
    )
    assert one_option.status_code == 422


def test_question_publish_controls_what_students_are_served(
    client: TestClient, admin_headers, curriculum, db: Session
):
    question = client.post(
        f"{API}/questions",
        headers=admin_headers,
        json={
            "skill_id": curriculum["foundation"].id,
            "question_type": "true_false",
            "prompt": "Is 2 + 2 = 4?",
            "answer_spec": {"value": True},
        },
    ).json()

    db.expire_all()
    assert db.get(Question, question["id"]).status == ReviewStatus.DRAFT

    client.post(f"{API}/questions/{question['id']}/publish", headers=admin_headers)
    db.expire_all()
    assert db.get(Question, question["id"]).status == ReviewStatus.PUBLISHED

    client.post(f"{API}/questions/{question['id']}/archive", headers=admin_headers)
    db.expire_all()
    assert db.get(Question, question["id"]).status == ReviewStatus.ARCHIVED


def test_question_import_is_a_dry_run_by_default(client: TestClient, admin_headers, curriculum):
    csv_body = (
        "question,type,options,correct_answer,explanation,difficulty,skill_slug,tags\n"
        f'"What is 2 + 3?",multiple_choice,4|5|6|7,5,"Add them.",1,'
        f'{curriculum["foundation"].slug},arithmetic\n'
        '"Broken row",multiple_choice,,,,,unknown-skill,\n'
    )
    files = {"file": ("bank.csv", io.BytesIO(csv_body.encode()), "text/csv")}

    dry = client.post(f"{API}/questions/import", headers=admin_headers, files=files)
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] is True
    assert body["parsed"] == 1
    assert len(body["errors"]) == 1
    assert "unknown skill" in body["errors"][0]["error"]

    before = client.get(f"{API}/questions", headers=admin_headers).json()["total"]

    files = {"file": ("bank.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    committed = client.post(
        f"{API}/questions/import?commit=true", headers=admin_headers, files=files
    )
    assert committed.status_code == 200
    assert committed.json()["created"] == 1

    after = client.get(f"{API}/questions", headers=admin_headers).json()
    assert after["total"] == before + 1
    # Imported content is always a draft, whatever the file claims.
    imported = next(row for row in after["items"] if row["prompt"] == "What is 2 + 3?")
    assert imported["status"] == "draft"


def test_question_with_attempts_cannot_be_deleted(
    client: TestClient, admin_headers, student_headers, curriculum
):
    """Deleting would silently rewrite a student's mastery history."""
    session = client.post(
        "/api/v1/practice/sessions",
        headers=student_headers,
        json={"skill_slug": curriculum["foundation"].slug, "target_questions": 1},
    ).json()
    served = client.get(
        f"/api/v1/practice/sessions/{session['id']}/next", headers=student_headers
    ).json()
    client.post(
        "/api/v1/practice/submit",
        headers=student_headers,
        json={"variant_id": served["variant_id"], "answer": {"value": "1"}},
    )

    response = client.delete(
        f"{API}/questions/{served['question_id']}", headers=admin_headers
    )
    assert response.status_code == 409
    assert "archive" in response.json()["detail"].lower()
