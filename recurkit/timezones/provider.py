from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum

from recurkit.errors import TimeZoneError

_PROBE = timedelta(days=1)


class LocalTimeKind(Enum):
    NORMAL = "normal"
    GAP = "gap"
    FOLD = "fold"


@dataclass(frozen=True)
class ResolvedTime:
    tzid: str
    local: datetime
    instant: datetime
    offset: timedelta
    kind: LocalTimeKind

    @property
    def wall(self) -> datetime:
        return (self.instant + self.offset).replace(tzinfo=None)

    @property
    def shifted(self) -> bool:
        return self.wall != self.local

    def aware(self) -> datetime:
        return self.wall.replace(tzinfo=timezone(self.offset, self.tzid))


def as_utc(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise TimeZoneError("an instant must be an aware datetime")
    return instant.astimezone(UTC)


class TimeZoneProvider(ABC):
    @abstractmethod
    def has_zone(self, tzid: str) -> bool:
        ...

    @abstractmethod
    def _offset(self, tzid: str, instant: datetime) -> timedelta:
        ...

    def check_zone(self, tzid: str) -> None:
        if not self.has_zone(tzid):
            raise TimeZoneError("unknown time zone", tzid=tzid)

    def utc_offset(self, tzid: str, instant: datetime) -> timedelta:
        self.check_zone(tzid)
        return self._offset(tzid, as_utc(instant))

    def to_local(self, tzid: str, instant: datetime) -> datetime:
        utc = as_utc(instant)
        return (utc + self.utc_offset(tzid, utc)).replace(tzinfo=None)

    def local_offsets(self, tzid: str, local: datetime) -> tuple[timedelta, ...]:
        if local.tzinfo is not None:
            raise TimeZoneError("a local time must be a naive datetime")
        self.check_zone(tzid)
        as_if_utc = local.replace(tzinfo=UTC)
        candidates = {
            self._offset(tzid, as_if_utc - _PROBE),
            self._offset(tzid, as_if_utc + _PROBE),
        }
        valid = [o for o in candidates if self._offset(tzid, as_if_utc - o) == o]
        return tuple(sorted(valid, reverse=True))

    def classify(self, tzid: str, local: datetime) -> LocalTimeKind:
        count = len(self.local_offsets(tzid, local))
        if count == 0:
            return LocalTimeKind.GAP
        return LocalTimeKind.FOLD if count > 1 else LocalTimeKind.NORMAL

    def exists(self, tzid: str, local: datetime) -> bool:
        return bool(self.local_offsets(tzid, local))

    def resolve(self, tzid: str, local: datetime) -> ResolvedTime:
        offsets = self.local_offsets(tzid, local)
        as_if_utc = local.replace(tzinfo=UTC)
        if offsets:
            kind = LocalTimeKind.FOLD if len(offsets) > 1 else LocalTimeKind.NORMAL
            instant = as_if_utc - offsets[0]
            return ResolvedTime(tzid, local, instant, offsets[0], kind)
        before = self._offset(tzid, as_if_utc - _PROBE)
        instant = as_if_utc - before
        return ResolvedTime(tzid, local, instant, self._offset(tzid, instant), LocalTimeKind.GAP)

    def localize(self, tzid: str, local: datetime) -> datetime:
        return self.resolve(tzid, local).aware()
