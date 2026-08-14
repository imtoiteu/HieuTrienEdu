"""What an administrator manages must be what a learner is served.

Every test here is a regression test for a real defect found by auditing the admin → database →
API → user path. They share a shape: **write through the admin API, read back through the public
API a browser uses**. Asserting on the admin response alone would have passed while every one of
these bugs was live — that is exactly how they survived.

Two failure modes recur, and both are invisible from the admin screen:

* **A publish switch that does nothing.** The row leaves the listing but its own URL still serves
  it, so a draft stays readable to anyone with the link.
* **A translation that can be read but never written.** The public endpoint calls ``localise`` on
  a field no admin endpoint accepts a translation for, so ``/vi`` is pinned to whatever the seed
  put there — and drifts silently as the English is edited.
"""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Achievement, Announcement, StudentProfile, TeacherProfile

# --------------------------------------------------------------------------------------
# unpublishing must actually hide things
# --------------------------------------------------------------------------------------


def test_unpublished_course_is_not_readable_by_its_own_url(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """Removing a course from the listings is not enough — the slug is a public address.

    The listing filtered on ``is_published`` but the detail endpoint did not, so a course pulled
    back to draft stayed fully readable at the URL that is already in search results and in
    anyone's history.
    """
    course = curriculum["course"]
    assert client.get(f"/api/v1/curriculum/courses/{course.slug}").status_code == 200

    response = client.post(
        f"/api/v1/admin/courses/{course.id}/status?status=draft", headers=admin_headers
    )
    assert response.status_code == 200

    assert client.get("/api/v1/curriculum/courses").json() == []
    assert client.get(f"/api/v1/curriculum/courses/{course.slug}").status_code == 404


def test_a_draft_course_hides_its_units_and_skills_too(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """A unit or skill URL is a second way in; closing only the course door leaves it open."""
    course = curriculum["course"]
    client.post(f"/api/v1/admin/courses/{course.id}/status?status=draft", headers=admin_headers)

    for path in (
        f"/api/v1/curriculum/units/{curriculum['unit'].slug}",
        f"/api/v1/curriculum/skills/{curriculum['foundation'].slug}",
        f"/api/v1/curriculum/topics/{curriculum['topic'].slug}/lessons",
    ):
        assert client.get(path).status_code == 404, path


def test_staff_can_still_preview_an_unpublished_course(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict, teacher_headers: dict
) -> None:
    """Hiding drafts from visitors must not stop the people who have to check them."""
    course = curriculum["course"]
    client.post(f"/api/v1/admin/courses/{course.id}/status?status=draft", headers=admin_headers)

    for headers in (admin_headers, teacher_headers):
        response = client.get(f"/api/v1/curriculum/courses/{course.slug}", headers=headers)
        assert response.status_code == 200
        assert response.json()["slug"] == course.slug


def test_unpublishing_a_teacher_removes_them_from_the_public_roster(
    client: TestClient, db: Session, teacher: TeacherProfile, admin_headers: dict
) -> None:
    """``is_published`` is the administrator's "show this person" switch.

    The public roster filtered only on the *account* being active, which made the switch
    decorative: the sole way to take someone off the site was to disable their login, which also
    locks them out of their own teacher dashboard.
    """
    client.post(f"/api/v1/admin/teachers/{teacher.id}/publish", headers=admin_headers)
    listed = client.get("/api/v1/tutoring/teachers").json()
    assert [row["id"] for row in listed] == [teacher.id]

    client.post(f"/api/v1/admin/teachers/{teacher.id}/unpublish", headers=admin_headers)
    assert client.get("/api/v1/tutoring/teachers").json() == []
    assert client.get(f"/api/v1/tutoring/teachers/{teacher.id}").status_code == 404


# --------------------------------------------------------------------------------------
# a field the public localises must be one the admin can translate
# --------------------------------------------------------------------------------------


def test_a_teacher_biography_can_be_written_in_vietnamese_and_is_served_that_way(
    client: TestClient, db: Session, teacher: TeacherProfile, admin_headers: dict
) -> None:
    """The public profile localised these fields; no admin endpoint accepted a translation.

    The visible symptom was worse than "English on /vi": editing the English biography left the
    seeded Vietnamese in place, so the two languages said different things and there was no way
    through the CMS to bring them back into line.
    """
    response = client.patch(
        f"/api/v1/admin/teachers/{teacher.id}",
        headers=admin_headers,
        json={
            "headline": "Mathematics lead",
            "bio": "Ten years teaching lower secondary mathematics.",
            "translations": {
                "vi": {
                    "headline": "Phụ trách chuyên môn Toán",
                    "bio": "Mười năm giảng dạy Toán trung học cơ sở.",
                }
            },
        },
    )
    assert response.status_code == 200
    # The editor has to be able to read its own translations back, or the next edit wipes them.
    assert response.json()["translations"]["vi"]["headline"] == "Phụ trách chuyên môn Toán"

    client.post(f"/api/v1/admin/teachers/{teacher.id}/publish", headers=admin_headers)

    vietnamese = client.get("/api/v1/tutoring/teachers?locale=vi").json()[0]
    assert vietnamese["headline"] == "Phụ trách chuyên môn Toán"
    assert vietnamese["bio"] == "Mười năm giảng dạy Toán trung học cơ sở."

    english = client.get("/api/v1/tutoring/teachers?locale=en").json()[0]
    assert english["headline"] == "Mathematics lead"


def test_a_testimonial_can_be_written_in_vietnamese(
    client: TestClient, db: Session, admin_headers: dict
) -> None:
    created = client.post(
        "/api/v1/admin/cms/testimonials",
        headers=admin_headers,
        json={
            "author_name": "Chị Lan",
            "author_role": "Parent",
            "quote": "My son finally enjoys mathematics.",
            "rating": 5,
            "is_published": True,
            "translations": {
                "vi": {"quote": "Con trai tôi đã yêu thích môn Toán.", "author_role": "Phụ huynh"}
            },
        },
    )
    assert created.status_code == 201
    assert created.json()["translations"]["vi"]["author_role"] == "Phụ huynh"

    vietnamese = client.get("/api/v1/site/testimonials?locale=vi").json()[0]
    assert vietnamese["quote"] == "Con trai tôi đã yêu thích môn Toán."
    assert vietnamese["author_role"] == "Phụ huynh"
    # A person's name is the same in both languages and is deliberately not translatable.
    assert vietnamese["author_name"] == "Chị Lan"

    assert client.get("/api/v1/site/testimonials?locale=en").json()[0]["quote"] == (
        "My son finally enjoys mathematics."
    )


def test_a_programme_can_be_written_in_vietnamese(
    client: TestClient, db: Session, admin_headers: dict
) -> None:
    created = client.post(
        "/api/v1/admin/programs",
        headers=admin_headers,
        json={
            "name": "One-to-one tutoring",
            "tagline": "A teacher to yourself",
            "format": "one_to_one",
            "grade_min": 6,
            "grade_max": 9,
            "price_vnd": 500000,
            "status": "published",
            "is_active": True,
            "translations": {
                "vi": {"name": "Gia sư 1 kèm 1", "tagline": "Một thầy một trò"}
            },
        },
    )
    assert created.status_code == 201

    vietnamese = client.get("/api/v1/tutoring/products?locale=vi").json()
    assert [row["name"] for row in vietnamese] == ["Gia sư 1 kèm 1"]
    assert client.get("/api/v1/tutoring/products?locale=en").json()[0]["name"] == (
        "One-to-one tutoring"
    )


def test_achievements_are_served_in_the_readers_language(
    client: TestClient, db: Session, curriculum: dict
) -> None:
    """The badge catalogue was hardcoded in the frontend, in English, in a second copy.

    Serving it means the screen shows what the server actually awards, and shows it in the
    student's language.
    """
    catalogue = client.get("/api/v1/progress/achievements?locale=en").json()
    assert [row["slug"] for row in catalogue] == ["first-steps"]
    assert catalogue[0]["name"] == "First Steps"

    achievement = db.query(Achievement).one()
    achievement.i18n = {"vi": {"name": "Bước đầu tiên", "description": "Trả lời câu hỏi đầu tiên"}}
    db.commit()

    vietnamese = client.get("/api/v1/progress/achievements?locale=vi").json()
    assert vietnamese[0]["name"] == "Bước đầu tiên"
    assert vietnamese[0]["description"] == "Trả lời câu hỏi đầu tiên"


# --------------------------------------------------------------------------------------
# per-locale rows must be filtered by locale
# --------------------------------------------------------------------------------------


def test_an_announcement_only_appears_in_its_own_language(
    client: TestClient, db: Session
) -> None:
    """Announcements carry a ``locale`` column that the public endpoint ignored.

    Every banner therefore showed on both sites at once — a Vietnamese Tết notice sat on top of
    the English pages, and vice versa.
    """
    db.add_all(
        [
            Announcement(
                title="Enrolment is open", kind="banner", locale="en", is_published=True
            ),
            Announcement(
                title="Đã mở đăng ký", kind="banner", locale="vi", is_published=True
            ),
        ]
    )
    db.commit()

    assert [row["title"] for row in client.get("/api/v1/site/announcements?locale=vi").json()] == [
        "Đã mở đăng ký"
    ]
    assert [row["title"] for row in client.get("/api/v1/site/announcements?locale=en").json()] == [
        "Enrolment is open"
    ]


def test_a_language_with_no_announcement_falls_back_rather_than_showing_nothing(
    client: TestClient, db: Session
) -> None:
    """Filtering must not turn "not translated yet" into an empty banner slot."""
    db.add(Announcement(title="Enrolment is open", kind="banner", locale="en", is_published=True))
    db.commit()

    assert [row["title"] for row in client.get("/api/v1/site/announcements?locale=vi").json()] == [
        "Enrolment is open"
    ]


def test_the_contact_acknowledgement_is_in_the_visitors_language(client: TestClient) -> None:
    payload = {"name": "Nguyễn Văn A", "email": "a@example.com", "message": "Xin tư vấn."}

    vietnamese = client.post("/api/v1/site/contact?locale=vi", json=payload).json()
    assert vietnamese["message"].startswith("Cảm ơn")

    english = client.post("/api/v1/site/contact?locale=en", json=payload).json()
    assert english["message"].startswith("Thank you")


# --------------------------------------------------------------------------------------
# the guarantee the whole audit was about
# --------------------------------------------------------------------------------------


def test_every_publicly_localised_model_has_an_admin_write_path() -> None:
    """A field the public localises but no admin endpoint can translate is a trap.

    It reads as working — ``/vi`` shows Vietnamese, because the seed put it there — right up to
    the first time somebody edits the row, after which the two languages disagree permanently and
    the CMS offers no way to reconcile them. That is how ``TeacherProfile`` shipped: listed in
    ``TRANSLATABLE``, localised on every public read, and unwritable.

    Guarding the class of bug rather than each instance means a *new* translatable model cannot be
    added with a read path and no write path. ``OWNER`` is the mapping that has to be kept
    honest; the test fails loudly if a model is added to ``TRANSLATABLE`` without one.
    """
    import importlib

    from app.api.v1.admin._translations import TRANSLATABLE

    # Which admin module owns each translatable model's write endpoints.
    OWNER = {
        "Subject": "curriculum", "Course": "curriculum", "Unit": "curriculum",
        "Topic": "curriculum", "Skill": "curriculum",
        "Lesson": "lessons", "Resource": "lessons",
        "Question": "questions",
        "TeacherProfile": "teachers",
        "Testimonial": "cms", "BlogPost": "cms", "SiteSetting": "cms",
        "TutoringProduct": "cms",
        "ClassGroup": "classes",
        "LiveSession": "classes",
        "ContentCategory": "categories",
    }

    unmapped = [model.__name__ for model in TRANSLATABLE if model.__name__ not in OWNER]
    assert not unmapped, (
        f"declared translatable but no admin module is recorded as owning it: {unmapped}. "
        "Add the write path, then map it here."
    )

    unwritable = []
    for model in TRANSLATABLE:
        module = importlib.import_module(f"app.api.v1.admin.{OWNER[model.__name__]}")
        source = inspect.getsource(module)
        if "apply_translations(" not in source or "read_translations(" not in source:
            unwritable.append(f"{model.__name__} (admin.{OWNER[model.__name__]})")
    assert not unwritable, (
        "public reads localise these, but their admin module neither stores nor returns "
        f"translations: {unwritable}"
    )


# --------------------------------------------------------------------------------------
# the admin screen has a language of its own
# --------------------------------------------------------------------------------------


def test_a_category_can_be_written_in_vietnamese(
    client: TestClient, db: Session, admin_headers: dict
) -> None:
    """Categories label courses and fill the public navigation, in both languages.

    The table had no ``i18n`` column at all, so there was one name for both sites — and the seed
    wrote Vietnamese into it, which put Vietnamese category names on ``/en``.
    """
    created = client.post(
        "/api/v1/admin/categories",
        headers=admin_headers,
        json={
            "name": "Exam preparation",
            "kind": "program",
            "is_published": True,
            "translations": {"vi": {"name": "Luyện thi"}},
        },
    )
    assert created.status_code == 201
    assert created.json()["translations"]["vi"]["name"] == "Luyện thi"

    assert [row["name"] for row in client.get("/api/v1/site/categories?locale=vi").json()] == [
        "Luyện thi"
    ]
    assert [row["name"] for row in client.get("/api/v1/site/categories?locale=en").json()] == [
        "Exam preparation"
    ]


def test_the_admin_reads_borrowed_parent_names_in_its_own_language(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """A row's own fields round-trip as English plus a blob; a parent's name is display only.

    The course list showed "Mathematics · Grade 7" to an administrator working entirely in
    Vietnamese, because ``subject_name`` is copied off the parent row and nothing localised it.
    There is no subject field on the course form to round-trip, so it is served ready to read.
    """
    subject = curriculum["subject"]
    patched = client.patch(
        f"/api/v1/admin/subjects/{subject.id}",
        headers=admin_headers,
        json={"name": subject.name, "translations": {"vi": {"name": "Toán học"}}},
    )
    assert patched.status_code == 200

    course_id = curriculum["course"].id
    vietnamese = client.get(
        f"/api/v1/admin/courses/{course_id}", headers={**admin_headers, "X-Locale": "vi"}
    ).json()
    english = client.get(
        f"/api/v1/admin/courses/{course_id}", headers={**admin_headers, "X-Locale": "en"}
    ).json()

    assert vietnamese["subject_name"] == "Toán học"
    assert english["subject_name"] == "Mathematics"
    # The course's *own* title stays the English column in both, because that is the field the
    # form edits; the Vietnamese travels beside it.
    assert vietnamese["title"] == english["title"] == "Mathematics — Grade 7"


def test_the_exercise_list_carries_both_languages(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """The exercise list shows the prompt, so it has to know the prompt in both languages.

    Every other translatable listing returned ``translations``; this one did not, which left the
    review queue English-only with no way to tell a translated question from an untranslated one.
    """
    question_id = client.get(
        "/api/v1/admin/questions?limit=1", headers=admin_headers
    ).json()["items"][0]["id"]
    client.patch(
        f"/api/v1/admin/questions/{question_id}",
        headers=admin_headers,
        json={"translations": {"vi": {"prompt": "{{a}} + {{b}} bằng bao nhiêu?"}}},
    )

    row = next(
        item
        for item in client.get("/api/v1/admin/questions", headers=admin_headers).json()["items"]
        if item["id"] == question_id
    )
    assert row["translations"]["vi"]["prompt"] == "{{a}} + {{b}} bằng bao nhiêu?"


# --------------------------------------------------------------------------------------
# duplicating must not quietly drop a language
# --------------------------------------------------------------------------------------


def test_duplicating_a_course_keeps_its_vietnamese(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """Duplication built the clone field by field and forgot ``i18n``.

    The copy arrived English-only on ``/vi`` while the original was fine, and nothing in the admin
    said why — so the fix has to reach the nested rows too, not just the course.
    """
    course = curriculum["course"]
    for path, payload in (
        (f"/api/v1/admin/courses/{course.id}", {"translations": {"vi": {"title": "Toán — Lớp 7"}}}),
        (
            f"/api/v1/admin/units/{curriculum['unit'].id}",
            {"translations": {"vi": {"title": "Phân số"}}},
        ),
        (
            f"/api/v1/admin/topics/{curriculum['topic'].id}",
            {"translations": {"vi": {"title": "Làm việc với phân số"}}},
        ),
    ):
        assert client.patch(path, headers=admin_headers, json=payload).status_code == 200

    clone = client.post(
        f"/api/v1/admin/courses/{course.id}/duplicate", headers=admin_headers
    ).json()
    assert clone["title"] == "Mathematics — Grade 7 (copy)"
    # The marker is a word the administrator reads, so it is translated too.
    assert clone["translations"]["vi"]["title"] == "Toán — Lớp 7 (bản sao)"

    tree = client.get(f"/api/v1/admin/courses/{clone['id']}", headers=admin_headers).json()
    unit = tree["units"][0]
    assert unit["translations"]["vi"]["title"] == "Phân số"
    assert unit["topics"][0]["translations"]["vi"]["title"] == "Làm việc với phân số"


def test_duplicating_a_lesson_keeps_its_vietnamese_body_as_a_draft(
    client: TestClient, db: Session, curriculum: dict, admin_headers: dict
) -> None:
    """The clone starts with an empty live body; each translation must follow the same rule.

    Copying the ``i18n`` blob verbatim would leave the Vietnamese body live on a lesson whose
    English body is still a draft — the two languages disagreeing about what is published.
    """
    created = client.post(
        "/api/v1/admin/lessons",
        headers=admin_headers,
        json={
            "title": "Adding fractions",
            "topic_id": curriculum["topic"].id,
            "status": "published",
            "blocks": [{"type": "text", "markdown": "Find a common denominator."}],
            "translations": {
                "vi": {
                    "title": "Cộng phân số",
                    "blocks": [{"type": "text", "markdown": "Tìm mẫu số chung."}],
                }
            },
        },
    )
    assert created.status_code == 201

    clone = client.post(
        f"/api/v1/admin/lessons/{created.json()['id']}/duplicate", headers=admin_headers
    ).json()
    assert clone["title"] == "Adding fractions (copy)"
    assert clone["translations"]["vi"]["title"] == "Cộng phân số (bản sao)"

    detail = client.get(f"/api/v1/admin/lessons/{clone['id']}", headers=admin_headers).json()
    vietnamese = detail["translations"]["vi"]
    assert vietnamese["draft_blocks"], "the Vietnamese body should survive as a draft"
    assert "blocks" not in vietnamese, "and must not be live while the English body is not"
    assert detail["blocks"] == []


def test_a_class_session_can_be_written_in_vietnamese_and_a_student_reads_it_that_way(
    client: TestClient, db: Session, student: StudentProfile, admin_headers: dict,
    student_headers: dict,
) -> None:
    """The two lines a student reads on their schedule: what the class is, and what it covers.

    ``live_sessions`` had no ``i18n`` column at all, so a Vietnamese student's timetable was in
    English however the rest of the site was set — and the class *name* beside it was English on
    the public read even though ``ClassGroup`` has been translatable all along.
    """
    group = client.post(
        "/api/v1/admin/classes",
        headers=admin_headers,
        json={
            "name": "Mathematics Grade 7 — Tuesday",
            "format": "group",
            "delivery_mode": "online_live",
            "capacity": 10,
            "translations": {"vi": {"name": "Toán lớp 7 — Thứ Ba"}},
        },
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    session = client.post(
        "/api/v1/admin/live-sessions",
        headers=admin_headers,
        json={
            "class_group_id": group_id,
            "title": "Session 1 — Fractions",
            "topic_summary": "Adding fractions with unlike denominators.",
            "starts_at": "2030-01-08T10:00:00Z",
            "ends_at": "2030-01-08T11:30:00Z",
            "translations": {
                "vi": {
                    "title": "Buổi 1 — Phân số",
                    "topic_summary": "Cộng phân số khác mẫu.",
                }
            },
        },
    )
    assert session.status_code == 201
    assert session.json()["translations"]["vi"]["title"] == "Buổi 1 — Phân số"

    enrolled = client.post(
        "/api/v1/admin/enrollments",
        headers=admin_headers,
        json={"student_id": student.id, "class_group_id": group_id, "status": "active"},
    )
    assert enrolled.status_code == 201

    schedule = client.get(
        "/api/v1/progress/dashboard", headers={**student_headers, "X-Locale": "vi"}
    ).json()["upcoming_sessions"]
    assert [row["title"] for row in schedule] == ["Buổi 1 — Phân số"]
    assert [row["class_name"] for row in schedule] == ["Toán lớp 7 — Thứ Ba"]

    english = client.get(
        "/api/v1/progress/dashboard", headers={**student_headers, "X-Locale": "en"}
    ).json()["upcoming_sessions"]
    assert [row["title"] for row in english] == ["Session 1 — Fractions"]
    assert [row["class_name"] for row in english] == ["Mathematics Grade 7 — Tuesday"]
