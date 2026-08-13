"""Declarative base and shared mixins."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# On PostgreSQL, use `jsonb` rather than `json`.
#
# This is not a micro-optimisation. PostgreSQL's `json` type stores the document as text and
# defines **no equality operator**, so any query that has to compare rows — most obviously
# `SELECT DISTINCT`, but also UNION and GROUP BY — fails outright with "could not identify an
# equality operator for type json" the moment a json column is in the select list. It also
# cannot be indexed usefully.
#
# SQLite has no such distinction and keeps plain JSON, so local development is unaffected. This
# only ever showed up on a real PostgreSQL deployment, which is precisely why it is pinned down
# here in one place rather than worked around at each call site.
JSON_COLUMN = JSON().with_variant(JSONB(), "postgresql")

# Explicit naming conventions make Alembic autogenerate produce stable, reversible migrations.
# Without them, unnamed constraints get backend-generated names and downgrades break.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Map bare ``dict``/``list`` annotations onto a portable JSON column so models can declare
    # ``Mapped[dict[str, Any]]`` without repeating ``mapped_column(JSON)`` everywhere.
    type_annotation_map = {
        dict[str, Any]: JSON_COLUMN,
        list[Any]: JSON_COLUMN,
        list[str]: JSON_COLUMN,
        list[dict[str, Any]]: JSON_COLUMN,
    }


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TranslatableMixin:
    """Adds the ``i18n`` translation blob to a content model.

    Shape: ``{"vi": {"title": "…", "summary": "…"}}``. Reads go through
    ``app.core.i18n.localise``, which falls back to the English column when a field is missing,
    so a partially-translated row renders rather than blanking. See that module for why this is a
    JSON column rather than per-language columns.
    """

    i18n: Mapped[dict[str, Any]] = mapped_column(JSON_COLUMN, default=dict, nullable=False)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
