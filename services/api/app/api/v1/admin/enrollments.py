"""Enrollment workflow: approve, reject, activate, complete, and reconcile payment."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    apply_sort,
    build_page,
    get_or_404,
    notify_user,
    paginate,
    record_audit,
)
from app.core.deps import RequestLocale
from app.core.i18n import DEFAULT_LOCALE, localise
from app.models import (
    ClassEnrollment,
    ClassGroup,
    EnrollmentStatus,
    NotificationKind,
    Order,
    OrderStatus,
    StudentProfile,
    TeacherProfile,
    User,
)
from app.services.payments import record_manual_payment

router = APIRouter(prefix="/enrollments", tags=["admin:enrollments"])

PAYMENT_STATUSES = {"unpaid", "partial", "paid", "refunded", "waived"}

# Which transitions the workflow permits. Rejecting an impossible move with a clear message beats
# silently allowing a completed enrollment to go back to pending.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    EnrollmentStatus.PENDING: {
        EnrollmentStatus.CONFIRMED,
        EnrollmentStatus.ACTIVE,
        EnrollmentStatus.CANCELLED,
    },
    EnrollmentStatus.CONFIRMED: {
        EnrollmentStatus.ACTIVE,
        EnrollmentStatus.CANCELLED,
        EnrollmentStatus.PENDING,
    },
    EnrollmentStatus.ACTIVE: {EnrollmentStatus.COMPLETED, EnrollmentStatus.CANCELLED},
    EnrollmentStatus.COMPLETED: {EnrollmentStatus.ACTIVE},
    EnrollmentStatus.CANCELLED: {EnrollmentStatus.PENDING, EnrollmentStatus.CONFIRMED},
}


class EnrollmentCreate(BaseModel):
    student_id: int
    class_group_id: int
    status: EnrollmentStatus = EnrollmentStatus.CONFIRMED
    payment_status: str = "unpaid"
    preferred_schedule: str | None = None
    requested_format: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)


class EnrollmentUpdate(BaseModel):
    status: EnrollmentStatus | None = None
    payment_status: str | None = None
    preferred_schedule: str | None = None
    requested_format: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)
    cancelled_reason: str | None = Field(default=None, max_length=2000)


def _row(enrollment: ClassEnrollment, locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
    student = enrollment.student
    group = enrollment.class_group
    return {
        "id": enrollment.id,
        "student_id": enrollment.student_id,
        "student_name": student.user.full_name if student and student.user else None,
        "student_email": student.user.email if student and student.user else None,
        "student_grade": student.grade if student else None,
        "class_group_id": enrollment.class_group_id,
        # Display only — the enrolment form picks a class by id, so the borrowed name arrives
        # in the administrator's language.
        "class_name": localise(group, "name", locale) if group else None,
        "format": group.format if group else None,
        "delivery_mode": group.delivery_mode if group else None,
        "teacher_id": group.teacher_id if group else None,
        "teacher_name": (
            group.teacher.user.full_name
            if group and group.teacher and group.teacher.user
            else None
        ),
        "status": enrollment.status,
        "payment_status": enrollment.payment_status,
        "preferred_schedule": enrollment.preferred_schedule,
        "requested_format": enrollment.requested_format,
        "notes": enrollment.notes,
        "cancelled_reason": enrollment.cancelled_reason,
        "order_id": enrollment.order_id,
        "enrolled_at": enrollment.enrolled_at,
        "approved_at": enrollment.approved_at,
        "created_at": enrollment.created_at,
    }


def _loaded(db, enrollment_id: int) -> ClassEnrollment:
    enrollment = db.scalar(
        select(ClassEnrollment)
        .where(ClassEnrollment.id == enrollment_id)
        .options(
            selectinload(ClassEnrollment.student).selectinload(StudentProfile.user),
            selectinload(ClassEnrollment.class_group)
            .selectinload(ClassGroup.teacher)
            .selectinload(TeacherProfile.user),
        )
    )
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    return enrollment


@router.get("")
def list_enrollments(
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
    enrollment_status: Annotated[EnrollmentStatus | None, Query(alias="status")] = None,
    payment_status: Annotated[str | None, Query(max_length=20)] = None,
    class_group_id: Annotated[int | None, Query()] = None,
    student_id: Annotated[int | None, Query()] = None,
    teacher_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(ClassEnrollment).options(
        selectinload(ClassEnrollment.student).selectinload(StudentProfile.user),
        selectinload(ClassEnrollment.class_group)
        .selectinload(ClassGroup.teacher)
        .selectinload(TeacherProfile.user),
    )
    if enrollment_status:
        query = query.where(ClassEnrollment.status == enrollment_status)
    if payment_status:
        query = query.where(ClassEnrollment.payment_status == payment_status)
    if class_group_id:
        query = query.where(ClassEnrollment.class_group_id == class_group_id)
    if student_id:
        query = query.where(ClassEnrollment.student_id == student_id)
    if teacher_id:
        query = query.where(
            ClassEnrollment.class_group_id.in_(
                select(ClassGroup.id).where(ClassGroup.teacher_id == teacher_id)
            )
        )
    if search:
        pattern = f"%{search}%"
        query = query.where(
            ClassEnrollment.student_id.in_(
                select(StudentProfile.id)
                .join(User, StudentProfile.user_id == User.id)
                .where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
            )
        )

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        ClassEnrollment,
        params,
        {
            "status": ClassEnrollment.status,
            "payment": ClassEnrollment.payment_status,
            "created_at": ClassEnrollment.created_at,
            "_default": ClassEnrollment.created_at,
        },
    )
    rows, total = paginate(db, query, params)
    return build_page([_row(row, locale) for row in rows], total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    payload: EnrollmentCreate, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """Place a student in a class directly — the counter-service path."""
    get_or_404(db, StudentProfile, payload.student_id, "Student")
    group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.id == payload.class_group_id)
        .options(selectinload(ClassGroup.enrollments))
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    if payload.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown payment status. Expected one of: {sorted(PAYMENT_STATUSES)}",
        )

    duplicate = db.scalar(
        select(ClassEnrollment).where(
            ClassEnrollment.class_group_id == group.id,
            ClassEnrollment.student_id == payload.student_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That student is already enrolled in this class",
        )

    # Count only places that actually occupy a seat. A cancelled enrollment should not keep a
    # class looking full.
    occupied = sum(
        1
        for e in group.enrollments
        if e.status in {EnrollmentStatus.CONFIRMED, EnrollmentStatus.ACTIVE}
    )
    if occupied >= group.capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"“{group.name}” is full ({occupied}/{group.capacity} places taken)",
        )

    now = dt.datetime.now(dt.UTC)
    enrollment = ClassEnrollment(
        **payload.model_dump(),
        approved_by_id=admin.id,
        approved_at=now if payload.status != EnrollmentStatus.PENDING else None,
        enrolled_at=now if payload.status == EnrollmentStatus.ACTIVE else None,
    )
    db.add(enrollment)
    db.flush()
    record_audit(
        db, admin, "create", "enrollment", enrollment.id,
        f"Enrolled student #{payload.student_id} in “{group.name}”",
    )
    db.commit()
    return _row(_loaded(db, enrollment.id), locale)


@router.get("/{enrollment_id}")
def get_enrollment(
    enrollment_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    enrollment = _loaded(db, enrollment_id)
    data = _row(enrollment, locale)
    if enrollment.order_id:
        order = db.get(Order, enrollment.order_id)
        data["order"] = (
            {
                "id": order.id,
                "reference": order.reference,
                "status": order.status,
                "total": order.total,
                "placed_at": order.placed_at,
            }
            if order
            else None
        )
    return data


@router.patch("/{enrollment_id}")
def update_enrollment(
    enrollment_id: int,
    payload: EnrollmentUpdate,
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
) -> dict[str, Any]:
    enrollment = _loaded(db, enrollment_id)
    fields = payload.model_dump(exclude_unset=True)

    if payload.payment_status is not None and payload.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown payment status. Expected one of: {sorted(PAYMENT_STATUSES)}",
        )

    if payload.status is not None and payload.status != enrollment.status:
        allowed = ALLOWED_TRANSITIONS.get(enrollment.status, set())
        if payload.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot move an enrollment from {enrollment.status} to {payload.status}. "
                    f"Allowed from here: {', '.join(sorted(allowed)) or 'nothing'}."
                ),
            )
        now = dt.datetime.now(dt.UTC)
        if payload.status in {EnrollmentStatus.CONFIRMED, EnrollmentStatus.ACTIVE}:
            enrollment.approved_by_id = admin.id
            enrollment.approved_at = enrollment.approved_at or now
        if payload.status == EnrollmentStatus.ACTIVE:
            enrollment.enrolled_at = enrollment.enrolled_at or now

        # Tell the student. This is the whole point of an approval workflow.
        student_user_id = (
            enrollment.student.user_id if enrollment.student else None
        )
        if student_user_id:
            notify_user(
                db,
                student_user_id,
                NotificationKind.ENROLLMENT_REQUESTED,
                f"Your enrollment is now {payload.status}",
                body=(
                    f"“{enrollment.class_group.name}”"
                    if enrollment.class_group
                    else None
                ),
                link_url="/dashboard",
                entity_type="enrollment",
                entity_id=enrollment.id,
            )

    previous = enrollment.status
    for key, value in fields.items():
        setattr(enrollment, key, value)

    record_audit(
        db, admin, "update", "enrollment", enrollment.id,
        f"Enrollment #{enrollment.id}: {previous} → {enrollment.status}",
        {k: str(v) for k, v in fields.items()},
    )
    db.commit()
    return _row(_loaded(db, enrollment_id), locale)


@router.post("/{enrollment_id}/approve")
def approve_enrollment(
    enrollment_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    return update_enrollment(
        enrollment_id, EnrollmentUpdate(status=EnrollmentStatus.CONFIRMED), db, admin
    )


@router.post("/{enrollment_id}/activate")
def activate_enrollment(
    enrollment_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    return update_enrollment(
        enrollment_id, EnrollmentUpdate(status=EnrollmentStatus.ACTIVE), db, admin
    )


@router.post("/{enrollment_id}/reject")
def reject_enrollment(
    enrollment_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    reason: Annotated[str | None, Query(max_length=2000)] = None,
) -> dict[str, Any]:
    return update_enrollment(
        enrollment_id,
        EnrollmentUpdate(status=EnrollmentStatus.CANCELLED, cancelled_reason=reason),
        db,
        admin,
    )


@router.post("/{enrollment_id}/mark-paid")
def mark_enrollment_paid(
    enrollment_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """Reconcile an offline payment against the linked order, if there is one."""
    enrollment = _loaded(db, enrollment_id)
    enrollment.payment_status = "paid"

    payment_id = None
    if enrollment.order_id:
        order = db.get(Order, enrollment.order_id)
        if order is not None and order.status != OrderStatus.PAID:
            payment = record_manual_payment(db, order)
            payment_id = payment.id

    record_audit(
        db, admin, "mark_paid", "enrollment", enrollment.id,
        f"Marked enrollment #{enrollment.id} as paid",
    )
    db.commit()
    result = _row(_loaded(db, enrollment_id), locale)
    result["payment_id"] = payment_id
    return result


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(enrollment_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    enrollment = _loaded(db, enrollment_id)
    db.delete(enrollment)
    record_audit(
        db, admin, "delete", "enrollment", enrollment_id, f"Deleted enrollment #{enrollment_id}"
    )
    db.commit()


# --------------------------------------------------------------------------------------
# orders
# --------------------------------------------------------------------------------------

orders_router = APIRouter(prefix="/orders", tags=["admin:orders"])


class MarkPaidRequest(BaseModel):
    amount: int | None = None
    reference: str | None = Field(default=None, max_length=160)


@orders_router.get("")
def list_orders(
    db: DbSession,
    admin: CurrentAdmin,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(Order).options(selectinload(Order.items), selectinload(Order.user))
    if order_status:
        query = query.where(Order.status == order_status)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Order.reference.ilike(pattern),
                Order.user_id.in_(
                    select(User.id).where(
                        or_(User.full_name.ilike(pattern), User.email.ilike(pattern))
                    )
                ),
            )
        )

    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(Order.created_at.desc())
    rows, total = paginate(db, query, params)
    items = [
        {
            "id": o.id,
            "reference": o.reference,
            "status": o.status,
            "total": o.total,
            "currency": o.currency,
            "placed_at": o.placed_at,
            "customer": o.user.full_name if o.user else None,
            "customer_email": o.user.email if o.user else None,
            "student_id": o.student_id,
            "items": [
                {"description": i.description, "line_total": i.line_total, "quantity": i.quantity}
                for i in o.items
            ],
        }
        for o in rows
    ]
    return build_page(items, total, params)


@orders_router.post("/{order_id}/mark-paid")
def mark_order_paid(
    order_id: int, payload: MarkPaidRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Reconcile an offline payment. This is what activates the student's place in the class."""
    order = get_or_404(db, Order, order_id, "Order")
    if order.status == OrderStatus.PAID:
        return {"order_id": order.id, "status": order.status, "already_paid": True}

    payment = record_manual_payment(db, order, amount=payload.amount, reference=payload.reference)

    # Keep the denormalised enrollment flag in step, so the enrollment list can be filtered on
    # payment without joining orders.
    for enrollment in db.scalars(
        select(ClassEnrollment).where(ClassEnrollment.order_id == order.id)
    ):
        enrollment.payment_status = "paid"

    record_audit(
        db, admin, "mark_paid", "order", order.id,
        f"Recorded payment for order {order.reference}",
        {"amount": payment.amount},
    )
    db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_id": payment.id,
        "amount": payment.amount,
        "already_paid": False,
    }


@orders_router.get("/stats")
def order_stats(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    rows = db.execute(
        select(Order.status, func.count(), func.coalesce(func.sum(Order.total), 0)).group_by(
            Order.status
        )
    ).all()
    return {
        "by_status": {
            row[0]: {"count": row[1], "total": int(row[2])} for row in rows
        },
        "revenue_vnd": int(
            sum(row[2] for row in rows if row[0] == OrderStatus.PAID)
        ),
    }
