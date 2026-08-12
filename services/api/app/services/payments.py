"""Payment provider abstraction.

**Implemented:** ``ManualProvider`` — bank transfer or cash at the centre, reconciled by an admin
marking the payment received. This is how the tutoring centre actually operates today, so it is a
complete, working implementation rather than a placeholder.

**Not implemented:** VNPay, MoMo, ZaloPay, Stripe. Each needs merchant credentials, a signed
callback endpoint and a sandbox account to test against — none of which exist yet. Their classes
are intentionally absent rather than stubbed out, so nothing in the UI can offer a payment method
that would fail. The interface below is what they will implement; see docs/DEPLOYMENT.md.

Amounts are integer **VND** throughout. VND has no minor unit, so there is no cents conversion.
"""

from __future__ import annotations

import datetime as dt
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, OrderStatus, Payment, PaymentStatus

__all__ = [
    "PaymentProvider",
    "ManualProvider",
    "get_payment_provider",
    "PaymentIntent",
    "create_order_reference",
    "record_manual_payment",
]


def create_order_reference() -> str:
    """Human-quotable order reference, e.g. ``HT-7Q2M4X8B``."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 — they get misread over the phone
    return "HT-" + "".join(secrets.choice(alphabet) for _ in range(8))


@dataclass
class PaymentIntent:
    provider: str
    reference: str
    amount: int
    currency: str = "VND"
    checkout_url: str | None = None
    instructions: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def create_intent(self, order: Order) -> PaymentIntent:
        ...


class ManualProvider(PaymentProvider):
    """Offline settlement: the family transfers or pays at the centre; an admin confirms."""

    name = "manual"

    @property
    def is_configured(self) -> bool:
        return True

    def create_intent(self, order: Order) -> PaymentIntent:
        return PaymentIntent(
            provider=self.name,
            reference=order.reference,
            amount=order.total,
            currency=order.currency,
            instructions=(
                "Transfer the total to the HieuTrienEducation account, or pay at the centre, "
                f"quoting reference {order.reference}. Your place is held for 48 hours and is "
                "confirmed as soon as we receive the payment."
            ),
            payload={"settlement": "offline", "hold_hours": 48},
        )


_PROVIDERS: dict[str, type[PaymentProvider]] = {"manual": ManualProvider}


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    key = (name or settings.payment_provider or "manual").lower()
    provider_class = _PROVIDERS.get(key)
    if provider_class is None:
        # An unconfigured gateway must never silently swallow a real order.
        return ManualProvider()
    return provider_class()


def record_manual_payment(
    db: Session, order: Order, *, amount: int | None = None, reference: str | None = None
) -> Payment:
    """Admin action: mark an order as settled and activate its enrollments."""
    from app.models import ClassEnrollment, EnrollmentStatus

    payment = Payment(
        order_id=order.id,
        provider="manual",
        provider_reference=reference,
        amount=amount if amount is not None else order.total,
        currency=order.currency,
        status=PaymentStatus.SUCCEEDED,
        paid_at=dt.datetime.now(dt.UTC),
    )
    db.add(payment)

    order.status = OrderStatus.PAID

    # Paying is what turns a held place into a real one.
    enrollments = db.query(ClassEnrollment).filter(ClassEnrollment.order_id == order.id).all()
    for enrollment in enrollments:
        enrollment.status = EnrollmentStatus.ACTIVE
        enrollment.enrolled_at = dt.datetime.now(dt.UTC)

    db.flush()
    return payment
