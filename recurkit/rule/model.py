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
    by_week_no: tuple[int, ...] = ()
    by_year_day: tuple[int, ...] = ()
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
        object.__setattr__(self, "by_week_no", _as_tuple(self.by_week_no))
        object.__setattr__(self, "by_year_day", _as_tuple(self.by_year_day))
        object.__setattr__(self, "by_month_day", _as_tuple(self.by_month_day))
        object.__setattr__(self, "by_day", _as_tuple(self.by_day))
        object.__setattr__(self, "by_set_pos", _as_tuple(self.by_set_pos))

    @property
    def has_by_parts(self) -> bool:
        """True if any BYxxx part other than BYSETPOS is present."""
        return bool(
            self.by_month or self.by_week_no or self.by_year_day or self.by_month_day or self.by_day
        )

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

    @classmethod
    def parse(cls, text: str, dtstart: date | datetime, tzid: str | None = None) -> Rule:
        """Parse and validate an RRULE for the given DTSTART.

        ``dtstart`` is a naive local (or floating) ``datetime``, a UTC-aware
        ``datetime`` or a ``date``; ``tzid`` names the zone of a naive local
        ``dtstart``. The zone itself is resolved only by ``recurrence_set``.
        Raises ``RuleSyntaxError`` or ``RuleValidationError``.
        """
        # Imported here: parser and validation import this module.
        from recurkit.rule.parser import parse_rrule
        from recurkit.rule.validation import validate

        return validate(parse_rrule(text, dtstart=dtstart, tzid=tzid))

    def to_text(self) -> str:
        """Serialize the rule parts (without DTSTART) as an RRULE value.

        FREQ always comes first (RRULE-04); default INTERVAL=1 and WKST=MO
        are omitted.
        """
        parts = [f"FREQ={self.freq}"]
        if self.interval != 1:
            parts.append(f"INTERVAL={self.interval}")
        if self.count is not None:
            parts.append(f"COUNT={self.count}")
        if self.until is not None:
            parts.append(f"UNTIL={format_date_value(self.until)}")
        if self.by_month:
            parts.append("BYMONTH=" + _join(self.by_month))
        if self.by_week_no:
            parts.append("BYWEEKNO=" + _join(self.by_week_no))
        if self.by_year_day:
            parts.append("BYYEARDAY=" + _join(self.by_year_day))
        if self.by_month_day:
            parts.append("BYMONTHDAY=" + _join(self.by_month_day))
        if self.by_day:
            parts.append("BYDAY=" + ",".join(item.to_text() for item in self.by_day))
        if self.by_set_pos:
            parts.append("BYSETPOS=" + _join(self.by_set_pos))
        if self.wkst is not Weekday.MO:
            parts.append(f"WKST={self.wkst.code}")
        return ";".join(parts)

    def __str__(self) -> str:
        return self.to_text()

    def require_dtstart(self) -> date | datetime:
        """Return DTSTART or fail: the generator needs it to derive missing parts."""
        if self.dtstart is None:
            raise ValueError("rule has no DTSTART; use Rule.parse(text, dtstart=...)")
        return self.dtstart


def _join(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def format_date_value(value: date | datetime) -> str:
    """Format a DATE or DATE-TIME value; UTC date-times get the ``Z`` suffix.

    Only naive and UTC values can be written: other offsets have no RFC 5545
    text form (DT-03).
    """
    if not isinstance(value, datetime):
        return f"{value.year:04d}{value.month:02d}{value.day:02d}"
    text = (
        f"{value.year:04d}{value.month:02d}{value.day:02d}"
        f"T{value.hour:02d}{value.minute:02d}{value.second:02d}"
    )
    if value.tzinfo is None:
        return text
    if value.utcoffset():
        raise ValueError("only naive or UTC date-times can be formatted")
    return text + "Z"
