"""The core learning journey, end to end through the API.

This is the test that matters most: register → login → practise → grade → mastery → recommend.
If it passes, the product's central claim works.
"""

from __future__ import annotations

from sqlalchemy import select

from app.adaptive import MASTERY_THRESHOLD
from app.models import Attempt, QuestionVariant, StudentSkillMastery


class TestPracticeLoop:
    def test_full_journey(self, client, curriculum):
        """Register, practise a skill to mastery, and confirm the recommendation changes."""
        registration = client.post(
            "/api/v1/auth/register",
            json={
                "email": "journey@example.com",
                "password": "JourneyPass1",
                "full_name": "Journey Student",
                "role": "student",
                "grade": 7,
            },
        )
        assert registration.status_code == 201
        headers = {
            "Authorization": f"Bearer {registration.json()['tokens']['access_token']}"
        }

        # A brand new student has no mastery anywhere.
        dashboard = client.get("/api/v1/progress/dashboard", headers=headers).json()
        assert dashboard["stats"]["total_attempts"] == 0
        assert dashboard["overall_mastery_percent"] == 0

        # The foundation skill should be recommended, and it must not be gated behind a
        # prerequisite the student has never been assessed on.
        recommendations = client.get(
            "/api/v1/practice/recommendations", headers=headers
        ).json()
        assert len(recommendations) > 0

        session = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions", "target_questions": 5},
            headers=headers,
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        masteries: list[float] = []
        for _ in range(6):
            served = client.get(
                f"/api/v1/practice/sessions/{session_id}/next", headers=headers
            )
            assert served.status_code == 200
            question = served.json()

            # The student-facing payload must never carry the answer.
            assert "answer" not in question
            assert "solution" not in question

            correct_value = _correct_value(client, question["variant_id"], headers)
            submission = client.post(
                "/api/v1/practice/submit",
                json={
                    "variant_id": question["variant_id"],
                    "answer": {"value": correct_value},
                    "session_id": session_id,
                    "time_spent_seconds": 30,
                },
                headers=headers,
            )
            assert submission.status_code == 200
            result = submission.json()
            assert result["is_correct"] is True
            assert result["gamification"]["xp_awarded"] > 0
            # The worked solution is released only after answering.
            assert len(result["solution"]) > 0
            masteries.append(result["mastery"]["after"])

        # Mastery must rise monotonically on a run of correct answers, and reach the threshold.
        assert masteries == sorted(masteries)
        assert masteries[-1] >= MASTERY_THRESHOLD

        dashboard = client.get("/api/v1/progress/dashboard", headers=headers).json()
        assert dashboard["stats"]["total_attempts"] == 6
        assert dashboard["stats"]["skills_mastered"] >= 1
        assert dashboard["overall_mastery_percent"] > 0
        assert len(dashboard["achievements"]) >= 1

        # Now that the foundation is mastered, it should no longer top the recommendations.
        recommendations = client.get(
            "/api/v1/practice/recommendations", headers=headers
        ).json()
        top_slugs = [rec["skill_slug"] for rec in recommendations]
        assert "equivalent-fractions" not in top_slugs[:1]

    def test_incorrect_answers_lower_mastery(self, client, curriculum, student_headers):
        session_id = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions"},
            headers=student_headers,
        ).json()["id"]

        question = client.get(
            f"/api/v1/practice/sessions/{session_id}/next", headers=student_headers
        ).json()

        result = client.post(
            "/api/v1/practice/submit",
            json={
                "variant_id": question["variant_id"],
                "answer": {"value": "-99999"},
                "session_id": session_id,
            },
            headers=student_headers,
        ).json()

        assert result["is_correct"] is False
        assert result["mastery"]["after"] < result["mastery"]["before"]
        assert result["correct_answer"] is not None
        # Effort still earns a little, which keeps struggling students engaged.
        assert result["gamification"]["xp_awarded"] > 0

    def test_hints_are_served_one_at_a_time(self, client, curriculum, student_headers):
        session_id = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions"},
            headers=student_headers,
        ).json()["id"]
        question = client.get(
            f"/api/v1/practice/sessions/{session_id}/next", headers=student_headers
        ).json()

        hint = client.get(
            f"/api/v1/practice/variants/{question['variant_id']}/hints/0",
            headers=student_headers,
        )
        assert hint.status_code == 200
        assert hint.json()["text"]

        missing = client.get(
            f"/api/v1/practice/variants/{question['variant_id']}/hints/99",
            headers=student_headers,
        )
        assert missing.status_code == 404

    def test_hints_reduce_the_evidential_value_of_a_correct_answer(
        self, client, curriculum, student_headers, db
    ):
        """Getting there after three hints should move mastery less than getting there unaided."""
        unaided = _single_attempt(client, student_headers, db, hints_used=0)
        hinted = _single_attempt(client, student_headers, db, hints_used=3)
        assert hinted < unaided

    def test_variant_is_persisted_for_audit(self, client, curriculum, student_headers, db):
        session_id = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions"},
            headers=student_headers,
        ).json()["id"]
        question = client.get(
            f"/api/v1/practice/sessions/{session_id}/next", headers=student_headers
        ).json()

        variant = db.get(QuestionVariant, question["variant_id"])
        assert variant is not None
        # The seed is what lets the server regenerate exactly what the student saw.
        assert variant.seed > 0
        assert variant.answer

    def test_session_completion(self, client, curriculum, student_headers):
        session_id = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions", "target_questions": 2},
            headers=student_headers,
        ).json()["id"]

        completed = client.post(
            f"/api/v1/practice/sessions/{session_id}/complete", headers=student_headers
        )
        assert completed.status_code == 200
        assert completed.json()["completed_at"] is not None

        # A completed session must not keep serving questions.
        assert (
            client.get(
                f"/api/v1/practice/sessions/{session_id}/next", headers=student_headers
            ).status_code
            == 409
        )

    def test_cannot_practise_anonymously(self, client, curriculum):
        assert (
            client.post(
                "/api/v1/practice/sessions", json={"skill_slug": "equivalent-fractions"}
            ).status_code
            == 401
        )

    def test_cannot_read_another_students_session(self, client, curriculum, student_headers):
        session_id = client.post(
            "/api/v1/practice/sessions",
            json={"skill_slug": "equivalent-fractions"},
            headers=student_headers,
        ).json()["id"]

        other = client.post(
            "/api/v1/auth/register",
            json={
                "email": "other@example.com",
                "password": "OtherPass1",
                "full_name": "Other Student",
                "role": "student",
            },
        ).json()
        other_headers = {"Authorization": f"Bearer {other['tokens']['access_token']}"}

        assert (
            client.get(
                f"/api/v1/practice/sessions/{session_id}", headers=other_headers
            ).status_code
            == 404
        )


class TestLearningPath:
    def test_path_locks_skills_behind_unmet_prerequisites(
        self, client, curriculum, student_headers
    ):
        path = client.get("/api/v1/practice/path/unit-fractions", headers=student_headers)
        assert path.status_code == 200
        nodes = {node["skill_slug"]: node for node in path.json()}

        assert nodes["equivalent-fractions"]["status"] == "available"
        # 'Adding fractions' depends on a skill in the same unit that has not been attempted.
        assert nodes["adding-fractions"]["status"] == "locked"
        assert "Equivalent fractions" in nodes["adding-fractions"]["blocked_by"]

    def test_path_unlocks_once_the_prerequisite_is_mastered(
        self, client, curriculum, student_headers, db, student
    ):
        record = StudentSkillMastery(
            student_id=student.id,
            skill_id=curriculum["foundation"].id,
            mastery_probability=0.97,
            attempts=6,
            correct=6,
        )
        db.add(record)
        db.commit()

        nodes = {
            node["skill_slug"]: node
            for node in client.get(
                "/api/v1/practice/path/unit-fractions", headers=student_headers
            ).json()
        }
        assert nodes["adding-fractions"]["status"] == "available"
        assert nodes["equivalent-fractions"]["status"] == "mastered"


class TestCurriculumEndpoints:
    def test_subjects_are_public(self, client, curriculum):
        response = client.get("/api/v1/curriculum/subjects")
        assert response.status_code == 200
        assert response.json()[0]["slug"] == "mathematics"

    def test_course_detail_includes_the_hierarchy(self, client, curriculum):
        course = client.get("/api/v1/curriculum/courses/math-7").json()
        assert course["units"][0]["topics"][0]["skills"]

    def test_skill_detail_exposes_the_graph(self, client, curriculum):
        skill = client.get("/api/v1/curriculum/skills/adding-fractions").json()
        assert [item["slug"] for item in skill["prerequisites"]] == ["equivalent-fractions"]
        assert skill["question_count"] == 3

    def test_unknown_slug_is_404(self, client, curriculum):
        assert client.get("/api/v1/curriculum/courses/nope").status_code == 404


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _correct_value(client, variant_id: int, headers: dict) -> float:
    """Read the stored answer directly — the API never exposes it, and tests need it."""
    from app.core.db import get_db
    from app.main import app

    session = next(app.dependency_overrides[get_db]())
    variant = session.get(QuestionVariant, variant_id)
    return variant.answer["value"]


def _single_attempt(client, headers: dict, db, *, hints_used: int) -> float:
    """Answer one question correctly and return the resulting mastery gain."""
    # A fresh student each time, so the two runs start from the same prior.
    email = f"hint-{hints_used}@example.com"
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "HintPass123",
            "full_name": "Hint Student",
            "role": "student",
        },
    ).json()
    own_headers = {"Authorization": f"Bearer {registration['tokens']['access_token']}"}

    session_id = client.post(
        "/api/v1/practice/sessions",
        json={"skill_slug": "equivalent-fractions"},
        headers=own_headers,
    ).json()["id"]
    question = client.get(
        f"/api/v1/practice/sessions/{session_id}/next", headers=own_headers
    ).json()

    variant = db.get(QuestionVariant, question["variant_id"])
    result = client.post(
        "/api/v1/practice/submit",
        json={
            "variant_id": question["variant_id"],
            "answer": {"value": variant.answer["value"]},
            "hints_used": hints_used,
            "session_id": session_id,
        },
        headers=own_headers,
    ).json()
    assert result["is_correct"] is True
    return result["mastery"]["after"]
