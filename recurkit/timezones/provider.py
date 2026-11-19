"""The TimeZoneProvider interface and the resolution rules of RFC 5545.

A provider only has to answer one question: what is the UTC offset of a zone
at a given instant. Everything about local wall-clock time is derived here,
once, for all providers:

- a local time that does not exist (spring forward) is a GAP; an explicit
  value in a gap is interpreted with the offset before the gap, so 02:30 in a
  one-hour gap means 03:30 (TZ-02);
- a local time that occurs twice (fall back) is a FOLD and refers to its
  first occurrence (TZ-01).

Assumption: two transitions of one zone are more than a day apart and every
offset is less than a day; this holds for all real zones.
"""

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
    """A local wall-clock time placed on the time line of a zone.

    ``local`` is the requested wall-clock time; ``wall`` is the wall-clock
    time actually shown at ``instant`` (they differ only for a GAP).
    """

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
        """The wall-clock time with a fixed-offset tzinfo named after the zone."""
        return self.wall.replace(tzinfo=timezone(self.offset, self.tzid))


def as_utc(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise TimeZoneError("an instant must be an aware datetime")
    return instant.astimezone(UTC)


class TimeZoneProvider(ABC):
    """Source of UTC offsets for named zones (IANA names such as ``Europe/Kyiv``)."""

    @abstractmethod
    def has_zone(self, tzid: str) -> bool:
        """True if the provider knows ``tzid``."""

    @abstractmethod
    def _offset(self, tzid: str, instant: datetime) -> timedelta:
        """UTC offset of a known zone at a UTC ``instant``."""

    def check_zone(self, tzid: str) -> None:
        """Raise :class:`TimeZoneError` for an unknown zone (TZ-04)."""
        if not self.has_zone(tzid):
            raise TimeZoneError("unknown time zone", tzid=tzid)

    def utc_offset(self, tzid: str, instant: datetime) -> timedelta:
        """UTC offset of ``tzid`` at an aware ``instant``."""
        self.check_zone(tzid)
        return self._offset(tzid, as_utc(instant))

    def to_local(self, tzid: str, instant: datetime) -> datetime:
        """Naive wall-clock time of ``tzid`` at an aware ``instant``."""
        utc = as_utc(instant)
        return (utc + self.utc_offset(tzid, utc)).replace(tzinfo=None)

    def local_offsets(self, tzid: str, local: datetime) -> tuple[timedelta, ...]:
        """Offsets under which the naive ``local`` time occurs, earliest instant first.

        One offset for a normal time, two for a FOLD, none for a GAP.
        """
        if local.tzinfo is not None:
            raise TimeZoneError("a local time must be a naive datetime")
        self.check_zone(tzid)
        as_if_utc = local.replace(tzinfo=UTC)
        candidates = {
            self._offset(tzid, as_if_utc - _PROBE),
            self._offset(tzid, as_if_utc + _PROBE),
        }
        valid = [o for o in candidates if self._offset(tzid, as_if_utc - o) == o]
        return tuple(sorted(valid, reverse=True))  # larger offset = earlier instant

    def classify(self, tzid: str, local: datetime) -> LocalTimeKind:
        count = len(self.local_offsets(tzid, local))
        if count == 0:
            return LocalTimeKind.GAP
        return LocalTimeKind.FOLD if count > 1 else LocalTimeKind.NORMAL

    def exists(self, tzid: str, local: datetime) -> bool:
        """False if ``local`` falls into a gap of ``tzid``."""
        return bool(self.local_offsets(tzid, local))

    def resolve(self, tzid: str, local: datetime) -> ResolvedTime:
        """Place an explicit local time (DTSTART, RDATE, EXDATE) on the time line.

        FOLD -> first occurrence (TZ-01); GAP -> offset before the gap (TZ-02).
        """
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
        """Shortcut: :meth:`resolve` returned as an aware datetime."""
        return self.resolve(tzid, local).aware()
