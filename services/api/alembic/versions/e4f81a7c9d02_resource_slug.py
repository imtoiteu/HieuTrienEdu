"""Give resources a slug so authored ones can be upserted.

Resources were CMS-only until now: an administrator created them by hand and nothing keyed them
back to a file. Grades 10-12 attach curated open-repository links (PhET, OpenStax, NASA) as
authored content, and the loader upserts authored content by slug — without one, re-running the
seed would duplicate every resource instead of updating it in place.

The column is nullable because both kinds of resource have to coexist: the authored ones carry a
slug from their YAML, and the ones an administrator adds through the CMS have nothing to key
against and leave it null. A unique index still holds across the authored ones, so two files
cannot claim the same slug. (SQLite and PostgreSQL both allow repeated NULLs under a unique
index, which is what makes the mixed population legal.)

Revision ID: e4f81a7c9d02
Revises: db7df6ee97c6
Create Date: 2026-08-14 09:12:04.881730
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f81a7c9d02'
down_revision: str | None = 'db7df6ee97c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(length=120), nullable=True))
        batch_op.create_index("ix_resources_slug", ["slug"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.drop_index("ix_resources_slug")
        batch_op.drop_column("slug")
