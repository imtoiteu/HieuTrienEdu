"""Live-class provider abstraction.

    LiveClassProvider
    ├── ManualProvider   (default — teacher pastes a meeting link)
    └── ZoomProvider     (Server-to-Server OAuth; active when credentials are configured)

The centre runs today by pasting Zoom/Meet links into a class, so ``ManualProvider`` is not a stub
— it is the honest default and it fully works. ``ZoomProvider`` implements Zoom's Server-to-Server
OAuth flow and meeting-creation API; it activates only when ``ZOOM_ACCOUNT_ID`` /
``ZOOM_CLIENT_ID`` / ``ZOOM_CLIENT_SECRET`` are all present, and reports itself unconfigured
otherwise rather than failing at call time.

**Not verified against live Zoom credentials.** The request/response shapes follow Zoom's
documented v2 API, but nobody has run this against a real Zoom account, so treat the first
production run as a smoke test. Documented in docs/DEPLOYMENT.md rather than glossed over.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

__all__ = ["LiveClassProvider", "ManualProvider", "ZoomProvider", "get_provider", "MeetingDetails"]


@dataclass
class MeetingDetails:
    provider: str
    meeting_id: str | None = None
    join_url: str | None = None
    host_url: str | None = None
    passcode: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class LiveClassProvider(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has everything it needs to make real API calls."""

    @abstractmethod
    def create_meeting(
        self,
        *,
        topic: str,
        starts_at: dt.datetime,
        duration_minutes: int,
        timezone: str = "Asia/Ho_Chi_Minh",
        agenda: str | None = None,
    ) -> MeetingDetails:
        ...

    def delete_meeting(self, meeting_id: str) -> bool:  # pragma: no cover - optional capability
        return False


class ManualProvider(LiveClassProvider):
    """No external service. The teacher supplies the join URL themselves."""

    name = "manual"

    @property
    def is_configured(self) -> bool:
        return True

    def create_meeting(self, *, topic: str, starts_at: dt.datetime, duration_minutes: int,
                       timezone: str = "Asia/Ho_Chi_Minh",
                       agenda: str | None = None) -> MeetingDetails:
        return MeetingDetails(
            provider=self.name,
            payload={
                "note": "Manual provider: a teacher or admin must paste the meeting link.",
                "topic": topic,
                "starts_at": starts_at.isoformat(),
                "duration_minutes": duration_minutes,
            },
        )


class ZoomProvider(LiveClassProvider):
    """Zoom Server-to-Server OAuth integration."""

    name = "zoom"
    TOKEN_URL = "https://zoom.us/oauth/token"
    API_BASE = "https://api.zoom.us/v2"

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: dt.datetime | None = None

    @property
    def is_configured(self) -> bool:
        return all(
            [settings.zoom_account_id, settings.zoom_client_id, settings.zoom_client_secret]
        )

    def _access_token(self) -> str:
        now = dt.datetime.now(dt.UTC)
        if self._token and self._token_expires_at and self._token_expires_at > now:
            return self._token

        response = httpx.post(
            self.TOKEN_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": settings.zoom_account_id,
            },
            auth=(settings.zoom_client_id or "", settings.zoom_client_secret or ""),
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        # Refresh a minute early to avoid racing the expiry on a slow request.
        self._token_expires_at = now + dt.timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
        return self._token

    def create_meeting(self, *, topic: str, starts_at: dt.datetime, duration_minutes: int,
                       timezone: str = "Asia/Ho_Chi_Minh",
                       agenda: str | None = None) -> MeetingDetails:
        if not self.is_configured:
            raise RuntimeError("Zoom is not configured — set ZOOM_ACCOUNT_ID/CLIENT_ID/SECRET")

        response = httpx.post(
            f"{self.API_BASE}/users/me/meetings",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            json={
                "topic": topic[:200],
                "type": 2,  # scheduled meeting
                "start_time": starts_at.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration": duration_minutes,
                "timezone": timezone,
                "agenda": (agenda or "")[:2000],
                "settings": {
                    "join_before_host": False,
                    "waiting_room": True,      # safeguarding: minors in the room
                    "mute_upon_entry": True,
                    "auto_recording": "cloud",
                },
            },
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        return MeetingDetails(
            provider=self.name,
            meeting_id=str(data.get("id")),
            join_url=data.get("join_url"),
            host_url=data.get("start_url"),
            passcode=data.get("password"),
            payload={k: data.get(k) for k in ("id", "topic", "start_time", "duration")},
        )

    def delete_meeting(self, meeting_id: str) -> bool:
        if not self.is_configured:
            return False
        response = httpx.delete(
            f"{self.API_BASE}/meetings/{meeting_id}",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            timeout=15.0,
        )
        return response.status_code in {204, 404}


_PROVIDERS: dict[str, type[LiveClassProvider]] = {
    "manual": ManualProvider,
    "zoom": ZoomProvider,
}

_instances: dict[str, LiveClassProvider] = {}


def get_provider(name: str | None = None) -> LiveClassProvider:
    """Return the configured provider, falling back to manual when unavailable."""
    key = (name or settings.live_class_provider or "manual").lower()
    provider_class = _PROVIDERS.get(key, ManualProvider)

    if key not in _instances:
        _instances[key] = provider_class()

    provider = _instances[key]
    if not provider.is_configured:
        # Degrade rather than break: a misconfigured Zoom must not stop a teacher scheduling a
        # class — they can still paste a link.
        return _instances.setdefault("manual", ManualProvider())
    return provider
