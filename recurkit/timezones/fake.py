"""Synthetic time zones for tests: transitions at any moment, by any amount.

They prove that RecurKit handles gaps and folds by definition, not because
real zone data happens to look a certain way: a 30-minute shift, a zone whose
clocks go back in spring ("negative" daylight saving time), a single
transition at an arbitrary instant.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta

from recurkit import calendar_math as cm
from recurkit.calendar_math import Weekday
from recurkit.timezones.provider import TimeZoneProvider


@dataclass(frozen=True)
class Transition:
    """From ``at`` (UTC) on, the zone uses ``offset``."""

    at: datetime
    offset: timedelta


@dataclass(frozen=True)
class AnnualSwitch:
    """A yearly transition such as "last Sunday of March at 01:00 UTC"."""

    month: int
    weekday: Weekday
    n: int
    at_utc: time

    def instant(self, year: int) -> datetime | None:
        day = cm.nth_weekday_of_month(year, self.month, self.weekday, self.n)
        if day is None:
            return None
        return datetime.combine(day, self.at_utc, tzinfo=UTC)


@dataclass(frozen=True)
class FakeZone:
    name: str
    initial_offset: timedelta
    transitions: tuple[Transition, ...] = ()
    _starts: tuple[datetime, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.transitions, key=lambda t: t.at))
        object.__setattr__(self, "transitions", ordered)
        object.__setattr__(self, "_starts", tuple(t.at for t in ordered))

    def offset_at(self, instant: datetime) -> timedelta:
        index = bisect_right(self._starts, instant)
        return self.initial_offset if index == 0 else self.transitions[index - 1].offset

    @classmethod
    def fixed(cls, name: str, offset: timedelta) -> FakeZone:
        return cls(name, offset)

    @classmethod
    def annual(
        cls,
        name: str,
        *,
        standard: timedelta,
        daylight: timedelta,
        start: AnnualSwitch,
        end: AnnualSwitch,
        years: Iterable[int],
    ) -> FakeZone:
        """A zone switching to ``daylight`` at ``start`` and back at ``end`` every year."""
        transitions = []
        for year in years:
            for switch, offset in ((start, daylight), (end, standard)):
                instant = switch.instant(year)
                if instant is not None:
                    transitions.append(Transition(instant, offset))
        return cls(name, standard, tuple(transitions))


_EU_START = AnnualSwitch(3, Weekday.SU, -1, time(1, 0))
_EU_END = AnnualSwitch(10, Weekday.SU, -1, time(1, 0))
_YEARS = range(1990, 2051)


def standard_zones() -> tuple[FakeZone, ...]:
    """The synthetic zones every FakeProvider knows by default."""
    hours = timedelta(hours=1)
    return (
        FakeZone.fixed("Fake/UTC", timedelta(0)),
        FakeZone.fixed("Fake/Plus0530", timedelta(hours=5, minutes=30)),
        FakeZone.annual(
            "Fake/EasternEurope",
            standard=2 * hours,
            daylight=3 * hours,
            start=_EU_START,
            end=_EU_END,
            years=_YEARS,
        ),
        FakeZone.annual(
            "Fake/HalfHour",
            standard=timedelta(hours=10, minutes=30),
            daylight=11 * hours,
            start=AnnualSwitch(10, Weekday.SU, 1, time(15, 30)),
            end=AnnualSwitch(4, Weekday.SU, 1, time(15, 0)),
            years=_YEARS,
        ),
        FakeZone.annual(
            "Fake/NegativeDST",
            standard=1 * hours,
            daylight=timedelta(0),
            start=AnnualSwitch(10, Weekday.SU, -1, time(1, 0)),
            end=AnnualSwitch(3, Weekday.SU, -1, time(1, 0)),
            years=_YEARS,
        ),
        FakeZone(
            "Fake/OneShot",
            timedelta(0),
            (
                Transition(
                    datetime(2026, 11, 16, 12, 34, tzinfo=UTC), timedelta(hours=1, minutes=15)
                ),
            ),
        ),
    )


class FakeProvider(TimeZoneProvider):
    """A provider backed by :class:`FakeZone` definitions."""

    def __init__(self, zones: Iterable[FakeZone] | None = None):
        self._zones = {zone.name: zone for zone in (standard_zones() if zones is None else zones)}

    def add(self, zone: FakeZone) -> None:
        self._zones[zone.name] = zone

    def has_zone(self, tzid: str) -> bool:
        return tzid in self._zones

    def _offset(self, tzid: str, instant: datetime) -> timedelta:
        return self._zones[tzid].offset_at(instant)

    @property
    def zone_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._zones))
