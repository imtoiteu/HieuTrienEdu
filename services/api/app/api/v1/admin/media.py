"""Media library: upload, catalogue, reuse and delete files.

Uploads are written to a directory on disk and served back as static URLs. That is a deliberate
choice over a stubbed S3 client: it is what a single-server tutoring centre actually needs, it
works with no configuration, and ``storage_public_base_url`` already exists for the day the files
move to object storage.

Security posture: the allow-list below is the *only* thing that can be uploaded. Extension and
declared MIME type must agree, filenames are regenerated rather than trusted, and everything is
written outside any directory the application would ever execute from.
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    build_page,
    get_or_404,
    paginate,
    record_audit,
)
from app.core.config import settings
from app.core.text import slugify
from app.models import Lesson, MediaAsset, MediaKind, Resource

router = APIRouter(prefix="/media", tags=["admin:media"])

# extension -> (allowed content types, kind). Nothing outside this map can be uploaded.
#
# Executable and script types are absent on purpose, and so are SVG and HTML: both can carry
# script that would run against the admin's own origin when opened from the library.
ALLOWED: dict[str, tuple[set[str], MediaKind]] = {
    ".jpg": ({"image/jpeg"}, MediaKind.IMAGE),
    ".jpeg": ({"image/jpeg"}, MediaKind.IMAGE),
    ".png": ({"image/png"}, MediaKind.IMAGE),
    ".gif": ({"image/gif"}, MediaKind.IMAGE),
    ".webp": ({"image/webp"}, MediaKind.IMAGE),
    ".avif": ({"image/avif"}, MediaKind.IMAGE),
    ".pdf": ({"application/pdf"}, MediaKind.DOCUMENT),
    ".doc": ({"application/msword"}, MediaKind.DOCUMENT),
    ".docx": (
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        MediaKind.DOCUMENT,
    ),
    ".ppt": ({"application/vnd.ms-powerpoint"}, MediaKind.DOCUMENT),
    ".pptx": (
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        MediaKind.DOCUMENT,
    ),
    ".xls": ({"application/vnd.ms-excel"}, MediaKind.DOCUMENT),
    ".xlsx": (
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        MediaKind.DOCUMENT,
    ),
    ".csv": ({"text/csv", "application/csv", "text/plain"}, MediaKind.DOCUMENT),
    ".md": ({"text/markdown", "text/plain"}, MediaKind.DOCUMENT),
    ".txt": ({"text/plain"}, MediaKind.DOCUMENT),
    ".mp3": ({"audio/mpeg", "audio/mp3"}, MediaKind.AUDIO),
    ".m4a": ({"audio/mp4", "audio/x-m4a"}, MediaKind.AUDIO),
    ".wav": ({"audio/wav", "audio/x-wav"}, MediaKind.AUDIO),
    ".ogg": ({"audio/ogg"}, MediaKind.AUDIO),
    ".mp4": ({"video/mp4"}, MediaKind.VIDEO),
    ".webm": ({"video/webm"}, MediaKind.VIDEO),
}

# Per-kind size ceilings. Video is capped low because self-hosting real video is not what this
# storage layer is for — the Video model exists to point at YouTube/Cloudflare instead.
MAX_BYTES: dict[MediaKind, int] = {
    MediaKind.IMAGE: 10 * 1024 * 1024,
    MediaKind.DOCUMENT: 50 * 1024 * 1024,
    MediaKind.AUDIO: 100 * 1024 * 1024,
    MediaKind.VIDEO: 200 * 1024 * 1024,
}

MEDIA_ROOT = Path(settings.content_dir).resolve().parent / "media"
PUBLIC_PREFIX = "/media"


class MediaUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=250)
    alt_text: str | None = Field(default=None, max_length=400)
    description: str | None = None
    tags: list[str] | None = None


def _row(asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "filename": asset.filename,
        "original_name": asset.original_name,
        "content_type": asset.content_type,
        "kind": asset.kind,
        "size_bytes": asset.size_bytes,
        "url": asset.url,
        "title": asset.title,
        "alt_text": asset.alt_text,
        "description": asset.description,
        "tags": asset.tags or [],
        "width": asset.width,
        "height": asset.height,
        "uploaded_by_id": asset.uploaded_by_id,
        "created_at": asset.created_at,
    }


def _safe_name(original: str) -> tuple[str, str]:
    """Return ``(stem, extension)`` derived from — never equal to — the uploaded name.

    The client-supplied filename is treated as a label, not a path. Rebuilding it from a slug of
    the stem plus a validated extension removes traversal (``../``), null bytes, and Windows
    device names in one step rather than by blocklisting each.
    """
    name = Path(original or "file").name
    suffix = Path(name).suffix.lower()
    stem = slugify(Path(name).stem, max_length=60, fallback="file")
    return stem, suffix


@router.get("")
def list_media(
    db: DbSession,
    admin: CurrentAdmin,
    kind: Annotated[MediaKind | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 40,
) -> dict[str, Any]:
    query = select(MediaAsset)
    if kind:
        query = query.where(MediaAsset.kind == kind)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                MediaAsset.original_name.ilike(pattern),
                MediaAsset.title.ilike(pattern),
                MediaAsset.description.ilike(pattern),
            )
        )
    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(MediaAsset.created_at.desc())
    rows, total = paginate(db, query, params)
    return build_page([_row(row) for row in rows], total, params)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    db: DbSession,
    admin: CurrentAdmin,
    file: UploadFile,
    title: Annotated[str | None, Query(max_length=250)] = None,
    alt_text: Annotated[str | None, Query(max_length=400)] = None,
) -> dict[str, Any]:
    stem, suffix = _safe_name(file.filename or "")

    if suffix not in ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"“{suffix or 'no extension'}” files cannot be uploaded. Allowed types: "
                f"{', '.join(sorted(ALLOWED))}"
            ),
        )
    allowed_types, kind = ALLOWED[suffix]

    declared = (file.content_type or "").split(";")[0].strip().lower()
    guessed = (mimetypes.guess_type(f"x{suffix}")[0] or "").lower()
    # The browser's declared type must match the extension. Neither alone is trustworthy, but a
    # mismatch between the two is a strong signal something is being smuggled.
    if declared and declared not in allowed_types and declared != guessed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"That file claims to be “{declared}” but has a “{suffix}” extension. "
                "Rename it or export it again."
            ),
        )

    raw = await file.read()
    limit = MAX_BYTES[kind]
    if len(raw) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"That file is {len(raw) // (1024 * 1024)}MB. The limit for {kind} files is "
                f"{limit // (1024 * 1024)}MB."
            ),
        )
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That file is empty"
        )

    checksum = hashlib.sha256(raw).hexdigest()
    existing = db.scalar(select(MediaAsset).where(MediaAsset.checksum == checksum))
    if existing is not None:
        # Identical bytes already in the library: hand back the existing asset instead of storing
        # a second copy under a different name.
        result = _row(existing)
        result["deduplicated"] = True
        return result

    target_dir = MEDIA_ROOT / kind
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{stem}-{checksum[:12]}{suffix}"
    path = target_dir / filename

    # Belt and braces: confirm the resolved path is still inside the media root.
    if not path.resolve().is_relative_to(MEDIA_ROOT.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name"
        )
    path.write_bytes(raw)

    base = (settings.storage_public_base_url or "").rstrip("/")
    url = f"{base}{PUBLIC_PREFIX}/{kind}/{filename}" if base else \
        f"{PUBLIC_PREFIX}/{kind}/{filename}"

    width = height = None
    if kind == MediaKind.IMAGE:
        width, height = _image_dimensions(raw)

    asset = MediaAsset(
        filename=filename,
        original_name=Path(file.filename or filename).name[:300],
        content_type=declared or guessed or "application/octet-stream",
        kind=kind,
        size_bytes=len(raw),
        url=url,
        checksum=checksum,
        title=title,
        alt_text=alt_text,
        width=width,
        height=height,
        uploaded_by_id=admin.id,
    )
    db.add(asset)
    db.flush()
    record_audit(
        db, admin, "upload", "media", asset.id,
        f"Uploaded {asset.original_name} ({len(raw) // 1024}KB)",
    )
    db.commit()
    db.refresh(asset)
    return _row(asset)


def _image_dimensions(raw: bytes) -> tuple[int | None, int | None]:
    """Read pixel dimensions from the file header without an image library.

    Only PNG, GIF and baseline JPEG are handled — enough to show a useful size in the library, and
    a missing dimension is not an error. Pulling in Pillow purely to display "1200 × 800" would be
    a large dependency for a cosmetic feature.
    """
    try:
        if raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) >= 24:
            return (
                int.from_bytes(raw[16:20], "big"),
                int.from_bytes(raw[20:24], "big"),
            )
        if raw[:6] in (b"GIF87a", b"GIF89a") and len(raw) >= 10:
            return (
                int.from_bytes(raw[6:8], "little"),
                int.from_bytes(raw[8:10], "little"),
            )
        if raw[:2] == b"\xff\xd8":
            index = 2
            while index < len(raw) - 9:
                if raw[index] != 0xFF:
                    index += 1
                    continue
                marker = raw[index + 1]
                # SOF0..SOF15, excluding the non-frame markers DHT/JPG/DAC.
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    return (
                        int.from_bytes(raw[index + 7 : index + 9], "big"),
                        int.from_bytes(raw[index + 5 : index + 7], "big"),
                    )
                index += 2 + int.from_bytes(raw[index + 2 : index + 4], "big")
    except (IndexError, ValueError):
        return None, None
    return None, None


@router.patch("/{asset_id}")
def update_media(
    asset_id: int, payload: MediaUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    asset = get_or_404(db, MediaAsset, asset_id, "File")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return _row(asset)


@router.get("/{asset_id}/usage")
def media_usage(asset_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Where a file is referenced, so an admin can see what deleting it would break."""
    asset = get_or_404(db, MediaAsset, asset_id, "File")

    resources = list(
        db.scalars(select(Resource).where(Resource.media_asset_id == asset_id))
    )
    # Lesson blocks reference files by URL, so this is a substring search rather than a join.
    lessons = [
        lesson
        for lesson in db.scalars(select(Lesson))
        if asset.url and asset.url in str(lesson.blocks or []) + str(lesson.draft_blocks or [])
    ]
    return {
        "asset_id": asset.id,
        "resources": [{"id": r.id, "title": r.title, "lesson_id": r.lesson_id}
                      for r in resources],
        "lessons": [{"id": lesson.id, "title": lesson.title, "slug": lesson.slug}
                    for lesson in lessons],
        "in_use": bool(resources or lessons),
    }


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    asset_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    force: Annotated[bool, Query()] = False,
) -> None:
    """Delete a file. Refuses while it is still referenced, unless forced."""
    asset = get_or_404(db, MediaAsset, asset_id, "File")
    usage = media_usage(asset_id, db, admin)
    if usage["in_use"] and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"That file is used by {len(usage['lessons'])} lesson(s) and "
                f"{len(usage['resources'])} material(s). Remove those references first, or "
                "delete it anyway."
            ),
        )

    path = MEDIA_ROOT / asset.kind / asset.filename
    try:
        if path.resolve().is_relative_to(MEDIA_ROOT.resolve()):
            path.unlink(missing_ok=True)
    except OSError:
        # A missing or unreadable file on disk must not block removing the catalogue entry —
        # otherwise a half-deleted upload is impossible to clean up from the UI.
        pass

    name = asset.original_name
    db.delete(asset)
    record_audit(db, admin, "delete", "media", asset_id, f"Deleted file {name}")
    db.commit()


@router.get("/stats/summary")
def media_stats(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    rows = db.execute(
        select(MediaAsset.kind, func.count(), func.coalesce(func.sum(MediaAsset.size_bytes), 0))
        .group_by(MediaAsset.kind)
    ).all()
    return {
        "by_kind": {row[0]: {"count": row[1], "bytes": int(row[2])} for row in rows},
        "total_files": sum(row[1] for row in rows),
        "total_bytes": int(sum(row[2] for row in rows)),
        "limits_mb": {str(k): v // (1024 * 1024) for k, v in MAX_BYTES.items()},
        "allowed_extensions": sorted(ALLOWED),
    }


__all__ = ["router", "MEDIA_ROOT", "PUBLIC_PREFIX"]
