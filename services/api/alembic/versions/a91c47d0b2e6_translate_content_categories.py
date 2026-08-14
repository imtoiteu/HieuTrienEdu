"""Add the translation column to content categories, and move the seeded Vietnamese into it.

Category names are public: they label courses, fill the site navigation and are what a visitor
filters by. The table had no ``i18n`` column, so there was one name for both languages — and the
seed wrote Vietnamese into it ("Toán", "Lớp 8", "Luyện thi vào 10"). That read correctly on ``/vi``
and put Vietnamese category names on the English site, which is the same bug as an untranslated
course, only inverted.

The data half matters as much as the column. Existing rows already hold Vietnamese in ``name``, so
the upgrade *moves* it into ``i18n.vi`` and writes the English name into the column, keyed by the
slug — which does not change, so nothing that references a category by slug or id is affected.
Rows the centre added itself are left exactly as they are: a name this migration does not
recognise is that administrator's own text, and guessing a translation for it would be worse than
leaving it in one language.

Revision ID: a91c47d0b2e6
Revises: f3a2c9b71d84
Create Date: 2026-08-14 11:02:18.339417
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text  # noqa: F401 — referenced by the JSONB variant below
from sqlalchemy.dialects import postgresql

revision: str = 'a91c47d0b2e6'
down_revision: str | None = 'f3a2c9b71d84'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# slug -> (English name, Vietnamese name). The slug is the stable key; it was derived from the
# Vietnamese name originally and deliberately stays that way.
SEEDED = {
    "toan": ("Mathematics", "Toán"),
    "vat-ly": ("Physics", "Vật lý"),
    "lop-6": ("Grade 6", "Lớp 6"),
    "lop-7": ("Grade 7", "Lớp 7"),
    "lop-8": ("Grade 8", "Lớp 8"),
    "lop-9": ("Grade 9", "Lớp 9"),
    "lop-10": ("Grade 10", "Lớp 10"),
    "lop-11": ("Grade 11", "Lớp 11"),
    "lop-12": ("Grade 12", "Lớp 12"),
    "luyen-thi": ("Exam preparation", "Luyện thi"),
    "luyen-thi-vao-10": ("Grade 10 entrance", "Luyện thi vào 10"),
    "hoc-them": ("Supplementary classes", "Học thêm"),
    "on-tap": ("Revision", "Ôn tập"),
    "hoc-1-1": ("One-to-one", "Học 1-1"),
    "hoc-nhom": ("Group classes", "Học nhóm"),
}


def upgrade() -> None:
    with op.batch_alter_table("content_categories", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "i18n",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
                nullable=False,
                server_default="{}",
            )
        )

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, slug, name, i18n FROM content_categories")).all()
    for row_id, slug, name, blob in rows:
        known = SEEDED.get(slug)
        if known is None:
            continue
        english, vietnamese = known
        if name != vietnamese:
            # Already edited by an administrator. Their text wins.
            continue
        existing = blob if isinstance(blob, dict) else json.loads(blob or "{}")
        existing = dict(existing)
        existing["vi"] = {**existing.get("vi", {}), "name": vietnamese}
        bind.execute(
            sa.text("UPDATE content_categories SET name = :name, i18n = :i18n WHERE id = :id"),
            {"name": english, "i18n": json.dumps(existing), "id": row_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, slug, i18n FROM content_categories")).all()
    for row_id, slug, blob in rows:
        known = SEEDED.get(slug)
        if known is None:
            continue
        existing = blob if isinstance(blob, dict) else json.loads(blob or "{}")
        vietnamese = (existing or {}).get("vi", {}).get("name")
        if vietnamese:
            bind.execute(
                sa.text("UPDATE content_categories SET name = :name WHERE id = :id"),
                {"name": vietnamese, "id": row_id},
            )

    with op.batch_alter_table("content_categories", schema=None) as batch_op:
        batch_op.drop_column("i18n")
