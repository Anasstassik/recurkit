from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from itertools import product

from recurkit.calendar_math import Weekday


class Frequency(StrEnum):
    SECONDLY = "SECONDLY"
    MINUTELY = "MINUTELY"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

    @property
    def rank(self) -> int:
        return _FREQUENCY_RANK[self]


_FREQUENCY_RANK = {frequency: rank for rank, frequency in enumerate(Frequency)}


@dataclass(frozen=True)
class WeekdayNum:
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
class RuleParts:
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
    by_hour: tuple[int, ...] = ()
    by_minute: tuple[int, ...] = ()
    by_second: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "freq", Frequency(self.freq))
        object.__setattr__(self, "wkst", Weekday(self.wkst))
        object.__setattr__(self, "by_month", _as_tuple(self.by_month))
        object.__setattr__(self, "by_week_no", _as_tuple(self.by_week_no))
        object.__setattr__(self, "by_year_day", _as_tuple(self.by_year_day))
        object.__setattr__(self, "by_month_day", _as_tuple(self.by_month_day))
        object.__setattr__(self, "by_day", _as_tuple(self.by_day))
        object.__setattr__(self, "by_set_pos", _as_tuple(self.by_set_pos))
        object.__setattr__(self, "by_hour", _as_tuple(self.by_hour))
        object.__setattr__(self, "by_minute", _as_tuple(self.by_minute))
        object.__setattr__(self, "by_second", _as_tuple(self.by_second))

    @property
    def has_by_parts(self) -> bool:
        return (
            bool(
                self.by_month
                or self.by_week_no
                or self.by_year_day
                or self.by_month_day
                or self.by_day
            )
            or self.has_time_parts
        )

    @property
    def has_time_parts(self) -> bool:
        return bool(self.by_hour or self.by_minute or self.by_second)

    def times_of_day(self) -> tuple[time, ...]:
        start = self.require_dtstart()
        if not isinstance(start, datetime):
            return ()
        hours = sorted(set(self.by_hour)) or [start.hour]
        minutes = sorted(set(self.by_minute)) or [start.minute]
        seconds = sorted(set(self.by_second)) or [start.second]
        return tuple(
            time(h, m, s, tzinfo=start.tzinfo) for h, m, s in product(hours, minutes, seconds)
        )

    @property
    def has_numeric_by_day(self) -> bool:
        return any(item.is_numeric for item in self.by_day)

    @property
    def is_all_day(self) -> bool:
        return isinstance(self.dtstart, date) and not isinstance(self.dtstart, datetime)

    @property
    def is_infinite(self) -> bool:
        return self.count is None and self.until is None

    @classmethod
    def parse(cls, text: str, dtstart: date | datetime, tzid: str | None = None) -> Rule:
        from recurkit.rule.parser import parse_rrule
        from recurkit.rule.validation import validate

        return validate(parse_rrule(text, dtstart=dtstart, tzid=tzid))

    def to_text(self) -> str:
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
        if self.by_hour:
            parts.append("BYHOUR=" + _join(self.by_hour))
        if self.by_minute:
            parts.append("BYMINUTE=" + _join(self.by_minute))
        if self.by_second:
            parts.append("BYSECOND=" + _join(self.by_second))
        if self.by_set_pos:
            parts.append("BYSETPOS=" + _join(self.by_set_pos))
        if self.wkst is not Weekday.MO:
            parts.append(f"WKST={self.wkst.code}")
        return ";".join(parts)

    def __str__(self) -> str:
        return self.to_text()

    def require_dtstart(self) -> date | datetime:
        if self.dtstart is None:
            raise ValueError("rule has no DTSTART; use Rule.parse(text, dtstart=...)")
        return self.dtstart


@dataclass(frozen=True)
class Rule(RuleParts):
    def __post_init__(self) -> None:
        super().__post_init__()
        from recurkit.errors import RuleValidationError
        from recurkit.rule.validation import find_violations

        violations = find_violations(self)
        if violations:
            raise violations[0]
        if self.dtstart is None:
            raise RuleValidationError("RULE-01", "a rule needs DTSTART to produce values")

    @classmethod
    def parse(cls, text: str, dtstart: date | datetime, tzid: str | None = None) -> Rule:
        from recurkit.rule.parser import parse_rrule
        from recurkit.rule.validation import validate

        return validate(parse_rrule(text, dtstart=dtstart, tzid=tzid))


def _join(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def format_date_value(value: date | datetime) -> str:
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
