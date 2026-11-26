from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum

from recurkit.errors import TimeZoneError

_PROBE = timedelta(days=1)
_EARLIEST = datetime.min.replace(tzinfo=UTC)
_LATEST = datetime.max.replace(tzinfo=UTC)


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


def probe(instant: datetime, delta: timedelta) -> datetime:
    try:
        return instant + delta
    except OverflowError:
        return _LATEST if delta > timedelta(0) else _EARLIEST


def out_of_range(tzid: str) -> TimeZoneError:
    return TimeZoneError("the time has no instant in years 1 to 9999 in this zone", tzid=tzid)


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

    def _safe_offset(self, tzid: str, instant: datetime) -> timedelta:
        try:
            return self._offset(tzid, instant)
        except OverflowError as error:
            raise out_of_range(tzid) from error

    def _instant(self, tzid: str, as_if_utc: datetime, offset: timedelta) -> datetime:
        try:
            return as_if_utc - offset
        except OverflowError as error:
            raise out_of_range(tzid) from error

    def utc_offset(self, tzid: str, instant: datetime) -> timedelta:
        self.check_zone(tzid)
        return self._safe_offset(tzid, as_utc(instant))

    def to_local(self, tzid: str, instant: datetime) -> datetime:
        utc = as_utc(instant)
        return self._instant(tzid, utc, -self.utc_offset(tzid, utc)).replace(tzinfo=None)

    def local_offsets(self, tzid: str, local: datetime) -> tuple[timedelta, ...]:
        if local.tzinfo is not None:
            raise TimeZoneError("a local time must be a naive datetime")
        self.check_zone(tzid)
        as_if_utc = local.replace(tzinfo=UTC)
        candidates = {
            self._safe_offset(tzid, probe(as_if_utc, -_PROBE)),
            self._safe_offset(tzid, probe(as_if_utc, _PROBE)),
        }
        valid = [
            o for o in candidates if self._safe_offset(tzid, self._instant(tzid, as_if_utc, o)) == o
        ]
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
        before = self._safe_offset(tzid, probe(as_if_utc, -_PROBE))
        instant = self._instant(tzid, as_if_utc, before)
        offset = self._safe_offset(tzid, instant)
        return ResolvedTime(tzid, local, instant, offset, LocalTimeKind.GAP)

    def localize(self, tzid: str, local: datetime) -> datetime:
        return self.resolve(tzid, local).aware()
