from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from recurkit.errors import TimeZoneError
from recurkit.timezones.provider import TimeZoneProvider


@lru_cache(maxsize=256)
def _load(tzid: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


class ZoneInfoProvider(TimeZoneProvider):
    def has_zone(self, tzid: str) -> bool:
        return bool(tzid) and _load(tzid) is not None

    def zone(self, tzid: str) -> ZoneInfo:
        zone = _load(tzid) if tzid else None
        if zone is None:
            raise TimeZoneError("unknown time zone", tzid=tzid)
        return zone

    def _offset(self, tzid: str, instant: datetime) -> timedelta:
        offset = instant.astimezone(self.zone(tzid)).utcoffset()
        if offset is None:  # pragma: no cover - ZoneInfo always returns an offset
            raise TimeZoneError("zone returned no UTC offset", tzid=tzid)
        return offset
