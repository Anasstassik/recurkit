"""Immutable model of an RFC 5545 recurrence rule (RRULE)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from recurkit.calendar_math import Weekday


class Frequency(StrEnum):
    """Supported values of the FREQ rule part (HOURLY and finer are out of scope)."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

    @property
    def rank(self) -> int:
        """Ordering by period length: DAILY < WEEKLY < MONTHLY < YEARLY."""
        return _FREQUENCY_RANK[self]


_FREQUENCY_RANK = {
    Frequency.DAILY: 0,
    Frequency.WEEKLY: 1,
    Frequency.MONTHLY: 2,
    Frequency.YEARLY: 3,
}


@dataclass(frozen=True)
class WeekdayNum:
    """One BYDAY value: a weekday with an optional ordinal, e.g. ``2TU``, ``-1FR``, ``MO``."""

    weekday: Weekday
    n: int | None = None

    def __post_init__(self) -> None:
        if self.n == 0:
            raise ValueError("BYDAY ordinal must not be zero")

    @property
    def is_numeric(self) -> bool:
        return self.n is not None

    def to_text(self) -> str:
        prefix = "" if self.n is None else str(self.n)
        return prefix + self.weekday.code

    def __str__(self) -> str:
        return self.to_text()


def _as_tuple[T](values: tuple[T, ...] | list[T]) -> tuple[T, ...]:
    return values if isinstance(values, tuple) else tuple(values)


@dataclass(frozen=True)
class Rule:
    """A recurrence rule with its DTSTART.

    Collections are tuples so the rule is hashable and immutable; list
    arguments are converted. ``dtstart`` is a naive ``datetime`` (local or
    floating time), a UTC-aware ``datetime`` or a ``date`` for all-day series;
    ``tzid`` names the zone of a local ``dtstart``.
    """

    freq: Frequency
    interval: int = 1
    count: int | None = None
    until: date | datetime | None = None
    by_month: tuple[int, ...] = ()
    by_month_day: tuple[int, ...] = ()
    by_day: tuple[WeekdayNum, ...] = ()
    by_set_pos: tuple[int, ...] = ()
    wkst: Weekday = Weekday.MO
    dtstart: date | datetime | None = None
    tzid: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "freq", Frequency(self.freq))
        object.__setattr__(self, "wkst", Weekday(self.wkst))
        object.__setattr__(self, "by_month", _as_tuple(self.by_month))
        object.__setattr__(self, "by_month_day", _as_tuple(self.by_month_day))
        object.__setattr__(self, "by_day", _as_tuple(self.by_day))
        object.__setattr__(self, "by_set_pos", _as_tuple(self.by_set_pos))

    @property
    def has_by_parts(self) -> bool:
        """True if any BYxxx part other than BYSETPOS is present."""
        return bool(self.by_month or self.by_month_day or self.by_day)

    @property
    def has_numeric_by_day(self) -> bool:
        return any(item.is_numeric for item in self.by_day)

    @property
    def is_all_day(self) -> bool:
        """True for a series of DATE values (DTSTART without a time)."""
        return isinstance(self.dtstart, date) and not isinstance(self.dtstart, datetime)

    @property
    def is_infinite(self) -> bool:
        return self.count is None and self.until is None

    def require_dtstart(self) -> date | datetime:
        """Return DTSTART or fail: the generator needs it to derive missing parts."""
        if self.dtstart is None:
            raise ValueError("rule has no DTSTART; use Rule.parse(text, dtstart=...)")
        return self.dtstart
