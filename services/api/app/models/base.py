"""Declarative base and shared mixins."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
        dict[str, Any]: JSON,
        list[Any]: JSON,
        list[str]: JSON,
        list[dict[str, Any]]: JSON,
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


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
