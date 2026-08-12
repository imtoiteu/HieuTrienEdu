"""convert json columns to jsonb on postgresql

Revision ID: a1b2c3d4e5f6
Revises: 66d0a4e1eb31
Create Date: 2026-08-12 16:20:00.000000

PostgreSQL's ``json`` type stores the document as text and defines **no equality operator**. Any
query that compares rows — ``SELECT DISTINCT``, ``UNION``, ``GROUP BY`` — fails outright with
"could not identify an equality operator for type json" as soon as a json column appears in the
select list. It also cannot be indexed usefully.

``jsonb`` has none of those limitations and is the type these columns should always have had.

The initial migration created them as ``json`` because the models used a portable ``sa.JSON``.
SQLite draws no distinction, so this only ever surfaced on a real PostgreSQL deployment.

Rather than enumerate every json column across 44 tables — a list that would silently rot as
tables are added — this walks ``information_schema`` and converts whatever it finds. That also
makes the migration correct for anyone whose database drifted from the initial schema.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "66d0a4e1eb31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `USING col::jsonb` is required: PostgreSQL will not implicitly cast json to jsonb in an ALTER.
_CONVERT = """
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND data_type = '{from_type}'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE {to_type} USING %I::{to_type}',
            r.table_name, r.column_name, r.column_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    # SQLite renders both as TEXT and has no ALTER COLUMN TYPE, so this is a PostgreSQL-only step.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_CONVERT.format(from_type="json", to_type="jsonb"))


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_CONVERT.format(from_type="jsonb", to_type="json"))
