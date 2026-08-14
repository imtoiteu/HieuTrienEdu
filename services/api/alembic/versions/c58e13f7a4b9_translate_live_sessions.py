"""Add the translation column to live sessions.

A session's ``title`` and ``topic_summary`` are the two lines a student and their parent read on
the class schedule — "what is the next lesson about". They were the last learner-facing prose
``localise`` could not reach: the times, the join link and the status are language-neutral facts,
but the sentence describing the lesson is not.

``server_default='{}'`` for the same reason as the earlier translation migrations: the table
already holds rows, and a nullable JSON column would make every read guard against ``None``.

Revision ID: c58e13f7a4b9
Revises: a91c47d0b2e6
Create Date: 2026-08-14 12:40:55.201884
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text  # noqa: F401 — referenced by the JSONB variant below
from sqlalchemy.dialects import postgresql

revision: str = 'c58e13f7a4b9'
down_revision: str | None = 'a91c47d0b2e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("live_sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "i18n",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("live_sessions", schema=None) as batch_op:
        batch_op.drop_column("i18n")
