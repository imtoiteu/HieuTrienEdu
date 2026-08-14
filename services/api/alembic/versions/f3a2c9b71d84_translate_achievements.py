"""Add the translation column to achievements.

Achievement names and descriptions are shown to the student on the achievements screen and in the
"you earned a badge" toast, so they belong in the reader's language like every other piece of
learner-facing content. They were the last table serving prose that ``localise`` could not reach.

``criteria`` deliberately stays untranslated: it is a machine-checkable rule, and a rule that
means something different per language would award badges inconsistently.

``server_default='{}'`` for the same reason as db7df6ee97c6 — the table already holds rows.

Revision ID: f3a2c9b71d84
Revises: e4f81a7c9d02
Create Date: 2026-08-14 10:12:04.771903
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text  # noqa: F401 — referenced by the JSONB variant below
from sqlalchemy.dialects import postgresql

revision: str = 'f3a2c9b71d84'
down_revision: str | None = 'e4f81a7c9d02'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("achievements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "i18n",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("achievements", schema=None) as batch_op:
        batch_op.drop_column("i18n")
