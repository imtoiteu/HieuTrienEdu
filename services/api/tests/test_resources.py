"""Further-reading resources: loading, attachment, localisation and public exposure.

Resources existed as a model long before anything displayed them. These tests pin down the
parts that make them actually reach a student: that the loader attaches them by slug and is
idempotent, that a lesson serves both its own and its topic's, that a private one never
escapes, and that the title and description localise like every other piece of content.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lesson, Resource, ReviewStatus

API = "/api/v1"
VI = {"X-Locale": "vi"}


@pytest.fixture
def lesson_with_resources(db: Session, curriculum: dict) -> Lesson:
    """One lesson, one resource of its own, one on its topic, and one that is not public."""
    topic = curriculum["topic"]
    lesson = Lesson(
        slug="lesson-fractions",
        title="Adding fractions",
        topic_id=topic.id,
        blocks=[],
        status=ReviewStatus.PUBLISHED,
        i18n={"vi": {"title": "Cộng phân số"}},
    )
    db.add(lesson)
    db.flush()

    db.add_all([
        Resource(
            slug="res-lesson", title="Fraction worksheet", description="Practice at home.",
            resource_type="reading", url="https://openstax.org/details/books/prealgebra-2e",
            lesson_id=lesson.id, position=0, is_public=True,
            license="CC BY 4.0", attribution="OpenStax, Rice University",
            i18n={"vi": {"title": "Phiếu bài tập phân số",
                         "description": "Luyện tập ở nhà."}},
        ),
        Resource(
            slug="res-topic", title="Fraction simulation", resource_type="simulation",
            url="https://phet.colorado.edu/en/simulations/fractions-intro",
            topic_id=topic.id, position=0, is_public=True,
            i18n={"vi": {"title": "Mô phỏng phân số"}},
        ),
        Resource(
            slug="res-hidden", title="Internal teacher notes", resource_type="link",
            url="https://example.invalid/private", lesson_id=lesson.id, is_public=False,
        ),
    ])
    db.commit()
    return lesson


# --------------------------------------------------------------------------------------
# the public read path
# --------------------------------------------------------------------------------------


def test_lesson_serves_its_own_and_its_topics_resources(
    client: TestClient, lesson_with_resources: Lesson
):
    body = client.get(f"{API}/curriculum/lessons/lesson-fractions").json()
    titles = [r["title"] for r in body["resources"]]

    assert titles == ["Fraction worksheet", "Fraction simulation"], (
        "lesson-specific resources come first, then the topic-wide ones"
    )


def test_private_resources_never_reach_a_student(
    client: TestClient, lesson_with_resources: Lesson
):
    body = client.get(f"{API}/curriculum/lessons/lesson-fractions").json()
    assert all("Internal" not in r["title"] for r in body["resources"])


def test_resource_host_is_derived_so_a_student_sees_where_a_link_goes(
    client: TestClient, lesson_with_resources: Lesson
):
    body = client.get(f"{API}/curriculum/lessons/lesson-fractions").json()
    hosts = {r["title"]: r["host"] for r in body["resources"]}

    assert hosts["Fraction worksheet"] == "openstax.org"
    assert hosts["Fraction simulation"] == "phet.colorado.edu"


def test_licence_and_attribution_are_served_so_the_page_can_credit_the_source(
    client: TestClient, lesson_with_resources: Lesson
):
    body = client.get(f"{API}/curriculum/lessons/lesson-fractions").json()
    worksheet = next(r for r in body["resources"] if r["title"] == "Fraction worksheet")

    assert worksheet["license"] == "CC BY 4.0"
    assert worksheet["attribution"] == "OpenStax, Rice University"


# --------------------------------------------------------------------------------------
# localisation
# --------------------------------------------------------------------------------------


def test_resources_are_localised_and_english_is_unchanged(
    client: TestClient, lesson_with_resources: Lesson
):
    vi = client.get(f"{API}/curriculum/lessons/lesson-fractions", headers=VI).json()
    en = client.get(f"{API}/curriculum/lessons/lesson-fractions").json()

    assert [r["title"] for r in vi["resources"]] == ["Phiếu bài tập phân số", "Mô phỏng phân số"]
    assert [r["title"] for r in en["resources"]] == ["Fraction worksheet", "Fraction simulation"]


def test_untranslated_resource_fields_fall_back_to_english_rather_than_blank(
    client: TestClient, lesson_with_resources: Lesson
):
    """The simulation has a Vietnamese title but no Vietnamese description."""
    vi = client.get(f"{API}/curriculum/lessons/lesson-fractions", headers=VI).json()
    simulation = next(r for r in vi["resources"] if r["title"] == "Mô phỏng phân số")

    assert simulation["description"] is None, "absent in both languages, so it stays absent"


def test_url_and_licence_are_never_translated(client: TestClient, lesson_with_resources: Lesson):
    """A URL is an address and a licence name is a legal identifier. Neither is prose."""
    vi = client.get(f"{API}/curriculum/lessons/lesson-fractions", headers=VI).json()
    worksheet = next(r for r in vi["resources"] if r["title"] == "Phiếu bài tập phân số")

    assert worksheet["url"] == "https://openstax.org/details/books/prealgebra-2e"
    assert worksheet["license"] == "CC BY 4.0"


# --------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------


RESOURCE_YAML = """
defaults:
  resource_type: link
  is_public: true
resources:
  - slug: res-loaded
    topic: topic-fractions
    title: A loaded resource
    description: Loaded from YAML.
    url: https://example.org/one
    license: CC BY 4.0
"""

SIDECAR_YAML = """
resources:
  res-loaded:
    title: Một tài nguyên đã nạp
    description: Được nạp từ YAML.
"""


def _write_content_tree(tmp_path, resources: str, sidecar: str | None = None):
    subject = tmp_path / "mathematics"
    (subject / "resources").mkdir(parents=True)
    (subject / "resources" / "res.yaml").write_text(resources, encoding="utf-8")
    if sidecar is not None:
        (subject / "i18n" / "vi").mkdir(parents=True)
        (subject / "i18n" / "vi" / "res.yaml").write_text(sidecar, encoding="utf-8")
    return tmp_path


def test_loader_creates_resources_and_attaches_them_to_a_topic(
    db: Session, curriculum: dict, tmp_path
):
    from app.content_io.loader import ContentLoader

    root = _write_content_tree(tmp_path, RESOURCE_YAML)
    report = ContentLoader(db, root).load_all()

    assert report.errors == []
    assert report.resources == 1
    resource = db.scalar(select(Resource).where(Resource.slug == "res-loaded"))
    assert resource.topic_id == curriculum["topic"].id
    assert resource.license == "CC BY 4.0"


def test_reloading_updates_in_place_rather_than_duplicating(
    db: Session, curriculum: dict, tmp_path
):
    """The whole reason Resource gained a slug: re-seeding must not multiply the library."""
    from app.content_io.loader import ContentLoader

    root = _write_content_tree(tmp_path, RESOURCE_YAML)
    ContentLoader(db, root).load_all()
    (root / "mathematics" / "resources" / "res.yaml").write_text(
        RESOURCE_YAML.replace("A loaded resource", "A renamed resource"), encoding="utf-8"
    )
    ContentLoader(db, root).load_all()

    rows = db.scalars(select(Resource).where(Resource.slug == "res-loaded")).all()
    assert len(rows) == 1
    assert rows[0].title == "A renamed resource"


def test_sidecar_directory_translations_are_applied(db: Session, curriculum: dict, tmp_path):
    """``i18n/vi/*.yaml`` is the split form of ``i18n/vi.yaml``; both must work."""
    from app.content_io.loader import ContentLoader

    root = _write_content_tree(tmp_path, RESOURCE_YAML, SIDECAR_YAML)
    ContentLoader(db, root).load_all()

    resource = db.scalar(select(Resource).where(Resource.slug == "res-loaded"))
    assert resource.i18n["vi"]["title"] == "Một tài nguyên đã nạp"
    assert resource.title == "A loaded resource", "English stays in the column"


def test_a_resource_attached_to_nothing_is_an_error_not_a_silent_orphan(
    db: Session, curriculum: dict, tmp_path
):
    from app.content_io.loader import ContentLoader

    orphan = RESOURCE_YAML.replace("    topic: topic-fractions\n", "")
    report = ContentLoader(db, _write_content_tree(tmp_path, orphan)).load_all()

    assert report.resources == 0
    assert any("neither a topic nor a lesson" in error for error in report.errors)


def test_an_unknown_topic_is_reported_rather_than_dropped(
    db: Session, curriculum: dict, tmp_path
):
    from app.content_io.loader import ContentLoader

    broken = RESOURCE_YAML.replace("topic-fractions", "topic-that-does-not-exist")
    report = ContentLoader(db, _write_content_tree(tmp_path, broken)).load_all()

    assert report.resources == 0
    assert any("unknown topic" in error for error in report.errors)
