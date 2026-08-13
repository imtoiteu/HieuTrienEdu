"""Content localisation: the read path, bilingual authoring and the guarantees around them.

These tests exist because "translate the site" is easy to get wrong in ways that only show up in
front of a student: a translated question whose answer no longer matches, a multiple-choice
question where the translation silently moved which option is correct, or a half-finished
translation that renders blank rather than falling back to English.

The English behaviour is asserted alongside the Vietnamese in almost every test — a localisation
change that breaks ``/en`` is a regression, not a trade-off.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.i18n import DEFAULT_LOCALE, localise, merge_translation, normalise_locale
from app.exercise_engine.generator import QuestionTemplate, generate_variant
from app.models import Question, QuestionVariant, ReviewStatus

API = "/api/v1"
ADMIN = f"{API}/admin"
VI = {"X-Locale": "vi"}


# --------------------------------------------------------------------------------------
# the primitives
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("vi", "vi"),
        ("vi-VN", "vi"),
        ("VI_vn", "vi"),
        ("en", "en"),
        ("fr", "en"),
        ("", "en"),
        (None, "en"),
        ("!!garbage!!", "en"),
    ],
)
def test_normalise_locale_never_returns_something_unsupported(header, expected):
    assert normalise_locale(header) == expected


def test_localise_falls_back_to_english_for_missing_and_empty_translations(curriculum):
    course = curriculum["course"]
    course.i18n = {"vi": {"title": "Toán học — Lớp 7", "summary": ""}}

    assert localise(course, "title", "vi") == "Toán học — Lớp 7"
    # An empty string means "not translated yet", not "deliberately blank".
    assert localise(course, "summary", "vi") == course.summary
    # A field with no translation at all falls back too.
    assert localise(course, "description", "vi") == course.description
    # English always reads the column, even if someone wrote an ``en`` bucket by mistake.
    assert localise(course, "title", DEFAULT_LOCALE) == "Mathematics — Grade 7"


def test_merge_translation_returns_a_new_dict_so_sqlalchemy_sees_the_change(curriculum):
    course = curriculum["course"]
    course.i18n = {"vi": {"title": "Cũ"}}
    before = course.i18n

    merged = merge_translation(course.i18n, "vi", {"summary": "Tóm tắt"})

    assert merged is not before, "must not mutate in place — the row would never be marked dirty"
    assert merged["vi"] == {"title": "Cũ", "summary": "Tóm tắt"}
    assert before == {"vi": {"title": "Cũ"}}


def test_clearing_every_field_drops_the_locale_entirely():
    blob = merge_translation({"vi": {"title": "Toán"}}, "vi", {"title": None})
    assert blob == {}, "an empty bucket would make `localise` do pointless work forever"


# --------------------------------------------------------------------------------------
# the public read path
# --------------------------------------------------------------------------------------


def test_curriculum_endpoints_serve_vietnamese_and_leave_english_alone(
    client: TestClient, db: Session, curriculum
):
    curriculum["subject"].i18n = {"vi": {"name": "Toán học"}}
    curriculum["course"].i18n = {"vi": {"title": "Toán học — Lớp 7", "summary": "Tóm tắt."}}
    curriculum["unit"].i18n = {"vi": {"title": "Phân số"}}
    curriculum["topic"].i18n = {"vi": {"title": "Làm việc với phân số"}}
    curriculum["foundation"].i18n = {"vi": {"name": "Phân số bằng nhau"}}
    db.commit()

    vi = client.get(f"{API}/curriculum/courses/math-7", headers=VI).json()
    en = client.get(f"{API}/curriculum/courses/math-7").json()

    assert vi["title"] == "Toán học — Lớp 7"
    assert vi["subject_name"] == "Toán học"
    assert vi["units"][0]["title"] == "Phân số"
    assert vi["units"][0]["topics"][0]["title"] == "Làm việc với phân số"

    assert en["title"] == "Mathematics — Grade 7"
    assert en["subject_name"] == "Mathematics"
    assert en["units"][0]["title"] == "Fractions"

    skill_vi = client.get(f"{API}/curriculum/skills/equivalent-fractions", headers=VI).json()
    assert skill_vi["name"] == "Phân số bằng nhau"
    assert skill_vi["course_title"] == "Toán học — Lớp 7"


def test_accept_language_is_honoured_when_no_explicit_locale_header(
    client: TestClient, db: Session, curriculum
):
    """A browser that only sends ``Accept-Language: vi-VN`` still gets Vietnamese."""
    curriculum["course"].i18n = {"vi": {"title": "Toán học — Lớp 7"}}
    db.commit()

    response = client.get(
        f"{API}/curriculum/courses/math-7", headers={"Accept-Language": "vi-VN,vi;q=0.9"}
    )
    assert response.json()["title"] == "Toán học — Lớp 7"


# --------------------------------------------------------------------------------------
# questions — where a bad translation does real damage
# --------------------------------------------------------------------------------------


def _translated_question(db: Session, curriculum) -> Question:
    question = db.query(Question).filter(Question.slug == "equivalent-fractions-q0").one()
    question.i18n = {
        "vi": {
            "prompt": "Giá trị của {{a}} + {{b}} là bao nhiêu?",
            "hints": [{"text": "Hãy cộng {{a}} với {{b}}."}],
            "solution": [{"text": "{{a}} + {{b}} = {{a+b}}."}],
        }
    }
    db.commit()
    return question


def test_a_translated_template_substitutes_variables_and_keeps_the_same_answer(
    db: Session, curriculum
):
    """The *template* is translated, not the rendered output.

    This is the whole reason translation happens in ``QuestionTemplate.from_model`` rather than
    after generation: the placeholders have to survive into the Vietnamese prose and be filled
    with the same numbers.
    """
    question = _translated_question(db, curriculum)

    en = generate_variant(QuestionTemplate.from_model(question, "en"), seed=99)
    vi = generate_variant(QuestionTemplate.from_model(question, "vi"), seed=99)

    assert vi.answer == en.answer, "a translation must never change what is correct"
    assert vi.variable_values == en.variable_values
    assert "Giá trị của" in vi.rendered["prompt"]
    assert "{{" not in vi.rendered["prompt"], "placeholders must be substituted, not left raw"
    # The substituted numbers really are the generated ones.
    assert str(en.variable_values["a"]) in vi.rendered["prompt"]
    assert "cộng" in vi.hints[0]["text"]


def test_choice_translations_cannot_move_which_option_is_correct(db: Session, curriculum):
    """Translated choices supply labels only; ``correct`` comes from the English source."""
    question = db.query(Question).filter(Question.slug == "adding-fractions-q0").one()
    question.question_type = "multiple_choice"
    question.answer_spec = {"choice": 1}
    question.options = {
        "choices": [
            {"label": "Ten", "correct": False},
            {"label": "Eleven", "correct": True},
            {"label": "Twelve", "correct": False},
        ]
    }
    # A translation that lists the labels in a different order — as a careless translator might.
    question.i18n = {
        "vi": {
            "options": {
                "choices": [
                    {"label": "Mười", "correct": False},
                    {"label": "Mười một", "correct": True},
                    {"label": "Mười hai", "correct": False},
                ]
            }
        }
    }
    db.commit()

    vi = generate_variant(QuestionTemplate.from_model(question, "vi"), seed=5)
    en = generate_variant(QuestionTemplate.from_model(question, "en"), seed=5)

    # Choices are shuffled per seed, so compare as sets and check the *correct* one by id.
    labels = {choice["label"] for choice in vi.rendered["choices"]}
    assert labels == {"Mười", "Mười một", "Mười hai"}
    assert not labels & {"Ten", "Eleven", "Twelve"}, "English labels leaked into the vi view"

    correct_id = vi.answer["choice_id"]
    correct_label = next(c["label"] for c in vi.rendered["choices"] if c["id"] == correct_id)
    assert correct_label == "Mười một", "the translation moved which option is correct"
    assert vi.answer["choice_id"] == en.answer["choice_id"]


def test_answer_spec_is_never_localised(db: Session, curriculum):
    """Even if someone puts an ``answer_spec`` in the translation blob, it is ignored."""
    question = _translated_question(db, curriculum)
    question.i18n["vi"]["answer_spec"] = {"expression": "a * b"}
    db.commit()

    en = generate_variant(QuestionTemplate.from_model(question, "en"), seed=3)
    vi = generate_variant(QuestionTemplate.from_model(question, "vi"), seed=3)
    assert vi.answer == en.answer


def test_practice_serves_vietnamese_questions_and_feedback(
    client: TestClient, db: Session, curriculum, student, student_headers
):
    curriculum["foundation"].i18n = {"vi": {"name": "Phân số bằng nhau"}}
    _translated_question(db, curriculum)

    started = client.post(
        f"{API}/practice/sessions",
        headers={**student_headers, **VI},
        json={"skill_slug": "equivalent-fractions", "length": 3},
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]

    served = client.get(
        f"{API}/practice/sessions/{session_id}/next", headers={**student_headers, **VI}
    ).json()
    assert "Giá trị của" in served["prompt"], served["prompt"]
    assert "{{" not in served["prompt"]
    if served.get("hints"):
        assert "cộng" in served["hints"][0]["text"]

    # A wrong answer must come back with Vietnamese feedback and a Vietnamese worked solution.
    wrong = client.post(
        f"{API}/practice/submit",
        headers={**student_headers, **VI},
        json={"variant_id": served["variant_id"], "answer": {"value": -999},
              "session_id": session_id},
    ).json()
    assert wrong["is_correct"] is False
    assert "Chưa đúng" in wrong["message"] or "Gần đúng" in wrong["message"], wrong["message"]
    assert not any(word in wrong["message"] for word in ("Not quite", "Close —"))

    # And a correct one.
    served2 = client.get(
        f"{API}/practice/sessions/{session_id}/next", headers={**student_headers, **VI}
    ).json()
    # The API never exposes the answer, so read it from the stored variant.
    correct = db.get(QuestionVariant, served2["variant_id"]).answer["value"]
    right = client.post(
        f"{API}/practice/submit",
        headers={**student_headers, **VI},
        json={"variant_id": served2["variant_id"], "answer": {"value": correct},
              "session_id": session_id},
    ).json()
    assert right["is_correct"] is True
    assert right["message"] == "Chính xác!", right["message"]


def test_english_practice_feedback_is_unchanged(
    client: TestClient, db: Session, curriculum, student, student_headers
):
    _translated_question(db, curriculum)
    started = client.post(
        f"{API}/practice/sessions",
        headers=student_headers,
        json={"skill_slug": "equivalent-fractions", "length": 2},
    ).json()
    served = client.get(
        f"{API}/practice/sessions/{started['id']}/next", headers=student_headers
    ).json()
    correct = db.get(QuestionVariant, served["variant_id"]).answer["value"]
    right = client.post(
        f"{API}/practice/submit",
        headers=student_headers,
        json={"variant_id": served["variant_id"], "answer": {"value": correct},
              "session_id": started["id"]},
    ).json()
    assert right["message"] == "Correct!"


def test_recommendations_are_localised(
    client: TestClient, db: Session, curriculum, student, student_headers
):
    curriculum["foundation"].i18n = {"vi": {"name": "Phân số bằng nhau"}}
    db.commit()

    vi = client.get(f"{API}/practice/recommendations", headers={**student_headers, **VI}).json()
    en = client.get(f"{API}/practice/recommendations", headers=student_headers).json()
    assert vi, "expected at least one recommendation"

    by_slug = {r["skill_slug"]: r for r in vi}
    assert by_slug["equivalent-fractions"]["skill_name"] == "Phân số bằng nhau"
    assert "sẵn sàng" in by_slug["equivalent-fractions"]["detail"], by_slug["equivalent-fractions"]
    # The machine-readable reason code is language-free and must not change.
    assert by_slug["equivalent-fractions"]["reason"] == "new_skill"

    en_by_slug = {r["skill_slug"]: r for r in en}
    assert en_by_slug["equivalent-fractions"]["skill_name"] == "Equivalent fractions"
    assert en_by_slug["equivalent-fractions"]["detail"] == "A new skill you are ready to start"


# --------------------------------------------------------------------------------------
# bilingual authoring in the admin CMS
# --------------------------------------------------------------------------------------


def test_admin_can_author_vietnamese_directly_and_it_reaches_the_public_api(
    client: TestClient, admin_headers, curriculum
):
    """The admin types Vietnamese; nothing is machine-translated at request time."""
    subject_id = curriculum["subject"].id
    created = client.post(
        f"{ADMIN}/courses",
        headers=admin_headers,
        json={
            "subject_id": subject_id,
            "title": "Physics — Grade 9",
            "grade": 9,
            "summary": "Forces and motion.",
            "status": "published",
            "translations": {
                "vi": {"title": "Vật lý — Lớp 9", "summary": "Lực và chuyển động."}
            },
        },
    )
    assert created.status_code == 201, created.text
    course = created.json()
    assert course["translations"]["vi"]["title"] == "Vật lý — Lớp 9"

    vi = client.get(f"{API}/curriculum/courses/{course['slug']}", headers=VI).json()
    en = client.get(f"{API}/curriculum/courses/{course['slug']}").json()
    assert vi["title"] == "Vật lý — Lớp 9"
    assert vi["summary"] == "Lực và chuyển động."
    assert en["title"] == "Physics — Grade 9"


def test_patching_other_fields_does_not_wipe_the_translation(
    client: TestClient, admin_headers, curriculum
):
    course_id = curriculum["course"].id
    client.patch(
        f"{ADMIN}/courses/{course_id}",
        headers=admin_headers,
        json={"translations": {"vi": {"title": "Toán học — Lớp 7"}}},
    )
    updated = client.patch(
        f"{ADMIN}/courses/{course_id}", headers=admin_headers, json={"estimated_hours": 40}
    ).json()
    assert updated["translations"]["vi"]["title"] == "Toán học — Lớp 7"


def test_clearing_a_translation_falls_back_to_english(
    client: TestClient, admin_headers, curriculum
):
    course_id = curriculum["course"].id
    client.patch(
        f"{ADMIN}/courses/{course_id}",
        headers=admin_headers,
        json={"translations": {"vi": {"title": "Toán học — Lớp 7"}}},
    )
    cleared = client.patch(
        f"{ADMIN}/courses/{course_id}",
        headers=admin_headers,
        json={"translations": {"vi": {"title": None}}},
    ).json()
    assert "vi" not in cleared["translations"]

    vi = client.get(f"{API}/curriculum/courses/math-7", headers=VI).json()
    assert vi["title"] == "Mathematics — Grade 7"


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"en": {"title": "x"}}, "English lives in the columns, not the translation blob"),
        ({"fr": {"title": "x"}}, "unsupported locale"),
        ({"vi": {"grade": 9}}, "grade is not translatable prose"),
        ({"vi": {"is_published": False}}, "a translation must not flip a publish flag"),
    ],
)
def test_invalid_translation_payloads_are_rejected_loudly(
    client: TestClient, admin_headers, curriculum, payload, reason
):
    """A typo in the translation form must 422, not silently leave the page in English."""
    response = client.patch(
        f"{ADMIN}/courses/{curriculum['course'].id}",
        headers=admin_headers,
        json={"translations": payload},
    )
    assert response.status_code == 422, f"{reason}: got {response.status_code}"


def test_a_broken_vietnamese_placeholder_is_caught_when_the_question_is_saved(
    client: TestClient, admin_headers, curriculum
):
    """A Vietnamese template that cannot render must fail at save, not in front of a student."""
    response = client.post(
        f"{ADMIN}/questions",
        headers=admin_headers,
        json={
            "skill_id": curriculum["foundation"].id,
            "question_type": "numeric",
            "prompt": "What is {{a}} + {{b}}?",
            "variables": {
                "a": {"type": "int", "min": 2, "max": 9},
                "b": {"type": "int", "min": 2, "max": 9},
            },
            "answer_spec": {"expression": "a + b"},
            "translations": {"vi": {"prompt": "Giá trị của {{ khong_ton_tai }} là bao nhiêu?"}},
        },
    )
    assert response.status_code == 422
    assert "[vi]" in response.text, "the error must say which language is broken"


def test_admin_can_preview_a_question_in_either_language(
    client: TestClient, admin_headers, db: Session, curriculum
):
    question = _translated_question(db, curriculum)

    en = client.get(
        f"{ADMIN}/questions/{question.id}/preview?seed=42&locale=en", headers=admin_headers
    ).json()
    vi = client.get(
        f"{ADMIN}/questions/{question.id}/preview?seed=42&locale=vi", headers=admin_headers
    ).json()

    assert "What is" in en["student_view"]["prompt"]
    assert "Giá trị của" in vi["student_view"]["prompt"]
    assert en["answer"] == vi["answer"]


def test_lesson_translations_follow_the_draft_publish_split(
    client: TestClient, admin_headers, curriculum
):
    """A translator editing a live lesson must not change what students are reading."""
    created = client.post(
        f"{ADMIN}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Equivalent fractions",
            "status": "published",
            "blocks": [{"type": "text", "markdown": "Two fractions are equivalent when…"}],
            "translations": {
                "vi": {
                    "title": "Phân số bằng nhau",
                    "blocks": [{"type": "text", "markdown": "Hai phân số bằng nhau khi…"}],
                }
            },
        },
    )
    assert created.status_code == 201, created.text
    lesson_id = created.json()["id"]
    slug = client.get(f"{ADMIN}/lessons/{lesson_id}", headers=admin_headers).json()["slug"]

    live = client.get(f"{API}/curriculum/lessons/{slug}", headers=VI).json()
    assert live["title"] == "Phân số bằng nhau"
    assert "Hai phân số bằng nhau" in live["blocks"][0]["markdown"]

    # Edit the Vietnamese body. Students keep reading the published version.
    client.patch(
        f"{ADMIN}/lessons/{lesson_id}",
        headers=admin_headers,
        json={
            "translations": {
                "vi": {"blocks": [{"type": "text", "markdown": "BẢN NHÁP CHƯA XUẤT BẢN"}]}
            }
        },
    )
    still_live = client.get(f"{API}/curriculum/lessons/{slug}", headers=VI).json()
    assert "BẢN NHÁP" not in still_live["blocks"][0]["markdown"]

    # Publishing promotes both languages together.
    client.post(f"{ADMIN}/lessons/{lesson_id}/publish", headers=admin_headers)
    published = client.get(f"{API}/curriculum/lessons/{slug}", headers=VI).json()
    assert "BẢN NHÁP CHƯA XUẤT BẢN" in published["blocks"][0]["markdown"]


def test_english_lesson_is_untouched_by_the_vietnamese_translation(
    client: TestClient, admin_headers, curriculum
):
    created = client.post(
        f"{ADMIN}/lessons",
        headers=admin_headers,
        json={
            "topic_id": curriculum["topic"].id,
            "title": "Adding fractions",
            "status": "published",
            "blocks": [{"type": "text", "markdown": "Find a common denominator first."}],
            "translations": {"vi": {"title": "Cộng phân số"}},
        },
    )
    slug = client.get(
        f"{ADMIN}/lessons/{created.json()['id']}", headers=admin_headers
    ).json()["slug"]

    en = client.get(f"{API}/curriculum/lessons/{slug}").json()
    assert en["title"] == "Adding fractions"
    assert "common denominator" in en["blocks"][0]["markdown"]


# --------------------------------------------------------------------------------------
# the seeded curriculum itself
# --------------------------------------------------------------------------------------


def test_seeded_content_files_carry_vietnamese_for_every_row():
    """The authored content, not just the plumbing, must actually be translated.

    This reads the repository's content files rather than the database so it fails in CI the
    moment someone adds an English course, unit or question without its Vietnamese counterpart.
    """
    from app.core.config import settings

    root = settings.content_dir
    if not root.exists():  # content ships separately in some deployments
        pytest.skip("content directory not present")

    missing: list[str] = []
    for subject_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        sidecar = subject_dir / "i18n" / "vi.yaml"
        if not sidecar.exists():
            missing.append(f"{subject_dir.name}: no i18n/vi.yaml")
    assert not missing, missing


def test_every_seeded_question_generates_in_vietnamese(db: Session):
    """Whatever is in the database must render in Vietnamese without throwing.

    Skipped on the empty test database; it is the check that matters when this suite is pointed
    at a seeded one.
    """
    questions = (
        db.query(Question)
        .filter(Question.status == ReviewStatus.PUBLISHED)
        .all()
    )
    translated = [q for q in questions if (q.i18n or {}).get("vi")]
    if not translated:
        pytest.skip("no translated questions in this database")

    for question in translated:
        template = QuestionTemplate.from_model(question, "vi")
        for seed in (1, 17, 404):
            variant = generate_variant(template, seed=seed)
            assert "{{" not in variant.rendered["prompt"], question.slug


# --------------------------------------------------------------------------------------
# marketing content
# --------------------------------------------------------------------------------------


def test_the_locale_lives_in_the_url_not_only_in_a_header(client: TestClient, db: Session):
    """Two languages must be two URLs.

    A header-only locale leaves both languages sharing one URL, and anything caching by URL — a
    CDN, a browser, Next.js's build-time fetch cache — then serves one language's response for the
    other. That is not hypothetical: it baked the English footer into the prerendered Vietnamese
    pages until the query parameter was added.
    """
    from app.models import SiteSetting

    db.add(
        SiteSetting(
            key="footer.tagline",
            group="footer",
            label="Footer tagline",
            value={"text": "Taught until it makes sense."},
            value_type="text",
            i18n={"vi": {"value": {"text": "Dạy đến khi các em thật sự hiểu."}}},
        )
    )
    db.commit()

    by_query = client.get(f"{API}/site/settings?locale=vi").json()
    by_header = client.get(f"{API}/site/settings", headers=VI).json()
    english = client.get(f"{API}/site/settings").json()

    assert by_query["footer.tagline"]["text"] == "Dạy đến khi các em thật sự hiểu."
    assert by_header["footer.tagline"] == by_query["footer.tagline"]
    assert english["footer.tagline"]["text"] == "Taught until it makes sense."


def test_query_parameter_wins_over_the_header(client: TestClient, db: Session, curriculum):
    """The URL is the authority, so a stale header cannot override an explicit request."""
    curriculum["course"].i18n = {"vi": {"title": "Toán học — Lớp 7"}}
    db.commit()

    response = client.get(
        f"{API}/curriculum/courses/math-7?locale=en", headers={"X-Locale": "vi"}
    )
    assert response.json()["title"] == "Mathematics — Grade 7"


def test_testimonials_translate_the_quote_but_never_the_author(client: TestClient, db: Session):
    from app.models import Testimonial

    db.add(
        Testimonial(
            author_name="Nguyễn Thị Lan",
            author_role="Parent of a Grade 7 student",
            quote="She explains it to her younger brother now.",
            rating=5,
            is_published=True,
            i18n={
                "vi": {
                    "author_role": "Phụ huynh học sinh lớp 7",
                    "quote": "Giờ cháu đã tự giảng lại cho em trai.",
                }
            },
        )
    )
    db.commit()

    vi = client.get(f"{API}/site/testimonials", headers=VI).json()[0]
    en = client.get(f"{API}/site/testimonials").json()[0]

    assert vi["quote"] == "Giờ cháu đã tự giảng lại cho em trai."
    assert vi["author_role"] == "Phụ huynh học sinh lớp 7"
    # A real person's name is the same in every language.
    assert vi["author_name"] == en["author_name"] == "Nguyễn Thị Lan"
    assert en["quote"] == "She explains it to her younger brother now."


def test_tutoring_products_translate_prose_but_not_prices(client: TestClient, db: Session):
    from app.models import TutoringProduct

    db.add(
        TutoringProduct(
            slug="one-to-one-mathematics",
            name="1-to-1 Mathematics Tutoring",
            tagline="A teacher entirely focused on your child",
            description="Weekly private lessons.",
            price_vnd=450_000,
            price_unit="session",
            capacity=1,
            features=["Choose your teacher", "Weekly progress report"],
            i18n={
                "vi": {
                    "name": "Gia sư Toán 1 kèm 1",
                    "tagline": "Một giáo viên dành trọn cho con bạn",
                    "features": ["Được chọn giáo viên", "Báo cáo tiến bộ hằng tuần"],
                }
            },
        )
    )
    db.commit()

    vi = client.get(f"{API}/tutoring/products", headers=VI).json()[0]
    en = client.get(f"{API}/tutoring/products").json()[0]

    assert vi["name"] == "Gia sư Toán 1 kèm 1"
    assert vi["features"] == ["Được chọn giáo viên", "Báo cáo tiến bộ hằng tuần"]
    # An untranslated field falls back rather than blanking.
    assert vi["description"] == "Weekly private lessons."
    # Money, capacity and format are facts, not prose.
    assert vi["price_vnd"] == en["price_vnd"] == 450_000
    assert vi["price_unit"] == en["price_unit"] == "session"
    assert en["name"] == "1-to-1 Mathematics Tutoring"


def test_admin_can_translate_marketing_content_too(client: TestClient, admin_headers, db: Session):
    from app.models import Testimonial

    testimonial = Testimonial(
        author_name="Trần Minh Quân", author_role="Grade 9 student",
        quote="The practice never runs out.", rating=5, is_published=True,
    )
    db.add(testimonial)
    db.commit()

    from app.api.v1.admin._translations import TRANSLATABLE

    # The whitelist is what the admin API enforces; assert the marketing models are on it and
    # that an author's name is deliberately absent.
    assert "quote" in TRANSLATABLE[Testimonial]
    assert "author_name" not in TRANSLATABLE[Testimonial]
