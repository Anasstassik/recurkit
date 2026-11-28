from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta

from recurkit.expand import occurrences
from recurkit.ical.vtimezone import Observance, VTimezone
from recurkit.timezones import TimeZoneProvider

_AHEAD = timedelta(days=800)
_LAST_LOCAL = datetime.max - timedelta(days=2)


def onsets(observance: Observance, until: datetime) -> Iterator[datetime]:
    yield observance.start
    if observance.rule is not None:
        for value in occurrences(observance.rule, until=until):
            if isinstance(value, datetime) and value != observance.start:
                yield value
    yield from (value for value in observance.rdates if value <= until)


class ZoneTransitions:
    def __init__(self, zone: VTimezone):
        self.zone = zone
        self.initial = min(zone.observances, key=lambda o: o.start).offset_from
        self.horizon: datetime | None = None
        self.starts: list[datetime] = []
        self.offsets: list[timedelta] = []

    def offset_at(self, instant: datetime) -> timedelta:
        local = instant.astimezone(UTC).replace(tzinfo=None)
        if self.horizon is None or local > self.horizon:
            self._cover(min(local, _LAST_LOCAL - _AHEAD) + _AHEAD)
        index = bisect_right(self.starts, instant)
        return self.initial if index == 0 else self.offsets[index - 1]

    def _cover(self, horizon: datetime) -> None:
        changes = sorted(
            ((local - o.offset_from).replace(tzinfo=UTC), o.offset_to)
            for o in self.zone.observances
            for local in onsets(o, horizon)
        )
        self.starts = [at for at, _ in changes]
        self.offsets = [offset for _, offset in changes]
        self.horizon = datetime.max if horizon == _LAST_LOCAL else horizon - timedelta(days=2)


class VTimezoneProvider(TimeZoneProvider):
    def __init__(self, zones: Iterable[VTimezone]):
        self._zones = {zone.tzid: ZoneTransitions(zone) for zone in zones}

    def has_zone(self, tzid: str) -> bool:
        return tzid in self._zones

    def _offset(self, tzid: str, instant: datetime) -> timedelta:
        return self._zones[tzid].offset_at(instant)

    def transitions(self, tzid: str, until: datetime) -> list[tuple[datetime, timedelta]]:
        self.check_zone(tzid)
        zone = self._zones[tzid]
        zone.offset_at(until)
        return [(at, o) for at, o in zip(zone.starts, zone.offsets, strict=True) if at <= until]
