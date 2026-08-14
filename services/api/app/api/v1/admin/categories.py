"""Admin-managed topics and categories.

Nothing in this module knows what "Toán" or "Lớp 8" is. The centre creates its own taxonomy from
the UI; the code only enforces that slugs stay unique, that a category cannot be its own ancestor,
and that deleting one does not silently orphan its children.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    build_page,
    diff_fields,
    get_or_404,
    next_position,
    paginate,
    record_audit,
)
from app.api.v1.admin._translations import (
    TranslationsPayload,
    apply_translations,
    read_translations,
)
from app.core.text import unique_slug
from app.models import CategoryKind, ContentCategory, CourseCategory, ProductCategory

router = APIRouter(prefix="/categories", tags=["admin:categories"])


class CategoryIn(TranslationsPayload):
    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=600)
    icon: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    kind: CategoryKind = CategoryKind.TOPIC
    parent_id: int | None = None
    is_published: bool = True
    is_visible_in_nav: bool = False
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class CategoryUpdate(TranslationsPayload):
    """Every field optional — a PATCH must be able to change one thing without resending the rest.

    ``model_fields_set`` is what distinguishes "not supplied" from "explicitly set to null", which
    matters for nullable columns such as ``parent_id``.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=600)
    icon: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    kind: CategoryKind | None = None
    parent_id: int | None = None
    is_published: bool | None = None
    is_visible_in_nav: bool | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    color: str | None = None
    kind: str
    parent_id: int | None = None
    position: int
    is_published: bool
    is_visible_in_nav: bool
    seo_title: str | None = None
    seo_description: str | None = None
    # Returned so one form round-trips both languages, exactly as every other translatable admin
    # read does. It is not a column, so it is lifted off ``i18n`` on the way out.
    translations: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _lift_translations(cls, data: Any) -> Any:
        if isinstance(data, ContentCategory):
            columns = {
                name: getattr(data, name)
                for name in cls.model_fields
                if name != "translations"
            }
            return {**columns, "translations": read_translations(data)}
        return data


class ReorderRequest(BaseModel):
    """Explicit id ordering. The client sends the whole list, which makes drag-and-drop reordering
    a single idempotent request instead of N swap operations that can interleave badly."""

    ids: list[int] = Field(min_length=1)


def _slug_taken(db, slug: str, exclude_id: int | None = None) -> bool:
    query = select(ContentCategory.id).where(ContentCategory.slug == slug)
    if exclude_id is not None:
        query = query.where(ContentCategory.id != exclude_id)
    return db.scalar(query) is not None


def _assert_no_cycle(db, category_id: int, parent_id: int | None) -> None:
    """Reject a parent change that would make the tree a ring.

    Without this an administrator can make A the parent of B and then B the parent of A, after
    which every recursive render of the tree hangs.
    """
    if parent_id is None:
        return
    if parent_id == category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A category cannot be its own parent",
        )
    seen = {category_id}
    cursor = db.get(ContentCategory, parent_id)
    while cursor is not None:
        if cursor.id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That parent would create a loop in the category tree",
            )
        seen.add(cursor.id)
        cursor = db.get(ContentCategory, cursor.parent_id) if cursor.parent_id else None


@router.get("")
def list_categories(
    db: DbSession,
    admin: CurrentAdmin,
    kind: Annotated[CategoryKind | None, Query()] = None,
    parent_id: Annotated[int | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    from app.api.v1.admin._common import PageParams

    query = select(ContentCategory)
    if kind:
        query = query.where(ContentCategory.kind == kind)
    if parent_id is not None:
        query = query.where(ContentCategory.parent_id == parent_id)
    if published is not None:
        query = query.where(ContentCategory.is_published.is_(published))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            ContentCategory.name.ilike(pattern) | ContentCategory.slug.ilike(pattern)
        )

    query = query.order_by(ContentCategory.position.asc(), ContentCategory.id.asc())
    params = PageParams(page=page, page_size=page_size)
    rows, total = paginate(db, query, params)

    # Usage counts let the admin see at a glance which categories are actually wired to content,
    # and warn before deleting one that is.
    course_counts = dict(
        db.execute(
            select(CourseCategory.category_id, func.count()).group_by(CourseCategory.category_id)
        ).all()
    )
    product_counts = dict(
        db.execute(
            select(ProductCategory.category_id, func.count()).group_by(
                ProductCategory.category_id
            )
        ).all()
    )

    items = []
    for row in rows:
        data = CategoryRead.model_validate(row).model_dump()
        data["course_count"] = course_counts.get(row.id, 0)
        data["product_count"] = product_counts.get(row.id, 0)
        items.append(data)
    return build_page(items, total, params)


@router.get("/tree")
def category_tree(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    """The whole taxonomy as a nested structure, for pickers and navigation editors."""
    rows = list(
        db.scalars(
            select(ContentCategory).order_by(
                ContentCategory.position.asc(), ContentCategory.id.asc()
            )
        )
    )
    by_parent: dict[int | None, list[ContentCategory]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)

    def build(parent_id: int | None) -> list[dict[str, Any]]:
        return [
            {
                **CategoryRead.model_validate(row).model_dump(),
                "children": build(row.id),
            }
            for row in by_parent.get(parent_id, [])
        ]

    return build(None)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryIn, db: DbSession, admin: CurrentAdmin) -> ContentCategory:
    _assert_no_cycle(db, 0, payload.parent_id)
    if payload.parent_id is not None:
        get_or_404(db, ContentCategory, payload.parent_id, "Parent category")

    slug = unique_slug(
        payload.slug or payload.name, lambda candidate: _slug_taken(db, candidate), max_length=140
    )
    category = ContentCategory(
        **payload.model_dump(exclude={"slug", "translations"}),
        slug=slug,
        position=next_position(db, ContentCategory, ContentCategory.parent_id == payload.parent_id),
    )
    db.add(category)
    db.flush()
    apply_translations(category, payload.translations)
    record_audit(
        db, admin, "create", "category", category.id, f"Created category “{category.name}”"
    )
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, db: DbSession, admin: CurrentAdmin) -> ContentCategory:
    return get_or_404(db, ContentCategory, category_id, "Category")


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int, payload: CategoryUpdate, db: DbSession, admin: CurrentAdmin
) -> ContentCategory:
    category = get_or_404(db, ContentCategory, category_id, "Category")
    # ``translations`` is not a column: it is merged into ``i18n`` below.
    fields = payload.model_dump(exclude_unset=True, exclude={"translations"})

    if "parent_id" in fields:
        _assert_no_cycle(db, category.id, fields["parent_id"])
        if fields["parent_id"] is not None:
            get_or_404(db, ContentCategory, fields["parent_id"], "Parent category")

    before = {key: getattr(category, key) for key in fields}

    if "slug" in fields and fields["slug"]:
        fields["slug"] = unique_slug(
            fields["slug"],
            lambda candidate: _slug_taken(db, candidate, exclude_id=category.id),
            max_length=140,
        )
    elif "slug" in fields:
        fields.pop("slug")

    for key, value in fields.items():
        setattr(category, key, value)

    apply_translations(category, payload.translations)

    record_audit(
        db,
        admin,
        "update",
        "category",
        category.id,
        f"Updated category “{category.name}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(category)
    return category


@router.post("/reorder", status_code=status.HTTP_200_OK)
def reorder_categories(
    payload: ReorderRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    rows = list(db.scalars(select(ContentCategory).where(ContentCategory.id.in_(payload.ids))))
    found = {row.id: row for row in rows}
    missing = [i for i in payload.ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown category ids: {missing}",
        )
    for index, category_id in enumerate(payload.ids, start=1):
        found[category_id].position = index
    record_audit(db, admin, "reorder", "category", None, f"Reordered {len(payload.ids)} categories")
    db.commit()
    return {"reordered": len(payload.ids)}


@router.post("/{category_id}/publish", response_model=CategoryRead)
def publish_category(category_id: int, db: DbSession, admin: CurrentAdmin) -> ContentCategory:
    return _set_published(db, admin, category_id, True)


@router.post("/{category_id}/unpublish", response_model=CategoryRead)
def unpublish_category(category_id: int, db: DbSession, admin: CurrentAdmin) -> ContentCategory:
    return _set_published(db, admin, category_id, False)


def _set_published(db, admin, category_id: int, value: bool) -> ContentCategory:
    category = get_or_404(db, ContentCategory, category_id, "Category")
    category.is_published = value
    record_audit(
        db,
        admin,
        "publish" if value else "unpublish",
        "category",
        category.id,
        f"{'Published' if value else 'Unpublished'} category “{category.name}”",
    )
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    reassign_children_to: Annotated[int | None, Query()] = None,
) -> None:
    """Delete a category, moving its children rather than cascading them into oblivion.

    The FK is ``ON DELETE SET NULL``, so children would survive as top-level categories — which is
    usually not what was meant. ``reassign_children_to`` makes the intent explicit.
    """
    category = get_or_404(db, ContentCategory, category_id, "Category")

    if reassign_children_to is not None:
        if reassign_children_to == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reassign children to the category being deleted",
            )
        get_or_404(db, ContentCategory, reassign_children_to, "Replacement category")

    children = list(
        db.scalars(select(ContentCategory).where(ContentCategory.parent_id == category_id))
    )
    for child in children:
        child.parent_id = reassign_children_to

    name = category.name
    db.delete(category)
    record_audit(
        db,
        admin,
        "delete",
        "category",
        category_id,
        f"Deleted category “{name}”",
        {"children_reassigned": len(children)},
    )
    db.commit()
