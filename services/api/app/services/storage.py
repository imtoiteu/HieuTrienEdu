"""Video and file storage abstraction.

Videos are never stored in PostgreSQL — the database holds only ``(provider, external_id)`` and
this module turns that pair into a playable URL. Switching from YouTube-unlisted (which is how a
small tutoring centre realistically starts) to Cloudflare Stream or S3 later is then a config
change plus a backfill, not a schema migration.

**Implemented today:** URL resolution for youtube, vimeo, cloudflare_stream, s3/r2 and a plain
``external`` passthrough.
**Not implemented:** uploading. There is no upload endpoint, because a real one needs signed
multipart URLs and a transcoding pipeline that would be dishonest to stub. See docs/DEPLOYMENT.md.
"""

from __future__ import annotations

from urllib.parse import quote

from app.core.config import settings

__all__ = ["playback_url", "thumbnail_url", "SUPPORTED_PROVIDERS"]

SUPPORTED_PROVIDERS = {
    "youtube",
    "vimeo",
    "cloudflare_stream",
    "s3",
    "r2",
    "external",
    "local",
}


def playback_url(provider: str, external_id: str) -> str | None:
    """Resolve a playable URL, or ``None`` when the provider is unknown."""
    if not external_id:
        return None

    provider = (provider or "").lower()

    if provider == "youtube":
        # nocookie domain avoids setting tracking cookies on students before they consent.
        return f"https://www.youtube-nocookie.com/embed/{quote(external_id, safe='')}"
    if provider == "vimeo":
        return f"https://player.vimeo.com/video/{quote(external_id, safe='')}"
    if provider == "cloudflare_stream":
        return f"https://customer-stream.cloudflarestream.com/{quote(external_id, safe='')}/iframe"
    if provider in {"s3", "r2", "local"}:
        base = (settings.storage_public_base_url or "").rstrip("/")
        if not base:
            return None
        return f"{base}/{external_id.lstrip('/')}"
    if provider == "external":
        return external_id

    return None


def thumbnail_url(provider: str, external_id: str) -> str | None:
    provider = (provider or "").lower()
    if provider == "youtube" and external_id:
        return f"https://i.ytimg.com/vi/{quote(external_id, safe='')}/hqdefault.jpg"
    return None
