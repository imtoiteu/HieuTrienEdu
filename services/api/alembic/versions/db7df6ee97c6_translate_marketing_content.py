"""Add the translation column to the public marketing content.

The curriculum got its ``i18n`` column in c75a7d56b2dc. This does the same for everything else a
visitor reads before they ever log in: tutoring products, class listings, testimonials, blog posts,
teacher profiles and the site settings behind the footer.

``server_default='{}'`` is required, not cosmetic. These tables already hold rows in the demo and
production databases, and a NOT NULL column added without a default fails the moment it is applied
to a populated table.

Revision ID: db7df6ee97c6
Revises: c75a7d56b2dc
Create Date: 2026-08-13 21:28:38.413412
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text  # noqa: F401 — referenced by the JSONB variant below
from sqlalchemy.dialects import postgresql

revision: str = 'db7df6ee97c6'
down_revision: str | None = 'c75a7d56b2dc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "blog_posts",
    "class_groups",
    "site_settings",
    "teacher_profiles",
    "testimonials",
    "tutoring_products",
)


def _i18n_column() -> sa.Column:
    return sa.Column(
        "i18n",
        sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
        nullable=False,
        server_default="{}",
    )


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(_i18n_column())


def downgrade() -> None:
    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("i18n")
