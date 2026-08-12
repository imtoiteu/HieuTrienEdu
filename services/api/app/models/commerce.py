"""Orders, payments and subscriptions.

Money is stored as **integer VND**. The Vietnamese đồng has no minor unit, so there is no need for
a cents column, and using floats for currency is a well-known source of drift.

No payment provider is wired up. ``services/payments.py`` defines the interface and ships a manual
(bank-transfer / cash-at-centre) provider, which is how the centre actually operates today.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import OrderStatus, PaymentStatus
from app.models.user import User


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    # The payer — usually a parent, but a student may buy a recorded course directly.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )

    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.DRAFT, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="VND", nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    promo_code: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    placed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutoring_products.id", ondelete="SET NULL")
    )
    class_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_groups.id", ondelete="SET NULL")
    )
    # Snapshot the name and price: if a product's price changes later, historical orders must not.
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    line_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(160))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="VND", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING, nullable=False)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    provider_payload: Mapped[dict[str, Any]] = mapped_column(default=dict)

    order: Mapped[Order] = relationship(back_populates="payments")


class Subscription(Base, TimestampMixin):
    """Recurring access to self-study content.

    Distinct from a fixed number of tutoring sessions.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )
    plan: Mapped[str] = mapped_column(String(40), default="practice_monthly", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    price_vnd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
