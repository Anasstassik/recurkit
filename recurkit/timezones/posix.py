"""Rule-based zones from POSIX TZ strings, e.g. ``EET-2EEST,M3.5.0/3,M10.5.0/4``.

The same format ends every compiled tz database file, so a POSIX string
describes the current rules of a real zone in one line. A :class:`PosixZone`
computes its transitions for any year on demand, which makes it a compact
synthetic zone for tests and a reference independent of ``zoneinfo``.

Grammar (POSIX.1, section 8.3)::

    std offset [dst [offset] [,start[/time],end[/time]]]

``offset`` is hours west of UTC (``-2`` is UTC+2); names are letters or
``<...>``; a date is ``Mm.w.d`` (weekday ``d`` of week ``w`` of month ``m``,
week 5 = last), ``Jn`` (day 1..365, February 29 never counted) or ``n``
(day 0..365, counting February 29).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from recurkit import calendar_math as cm
from recurkit.calendar_math import Weekday
from recurkit.errors import TimeZoneError

_NAME = r"(?:[A-Za-z]{3,}|<[A-Za-z0-9+-]{1,}>)"
_TIME = r"[+-]?\d{1,3}(?::\d{1,2}){0,2}"
_DATE = r"(?:M\d{1,2}\.\d\.\d|J\d{1,3}|\d{1,3})"
_POSIX = re.compile(
    rf"^(?P<std>{_NAME})(?P<std_off>{_TIME})"
    rf"(?:(?P<dst>{_NAME})(?P<dst_off>{_TIME})?"
    rf"(?:,(?P<start>{_DATE})(?:/(?P<start_time>{_TIME}))?"
    rf",(?P<end>{_DATE})(?:/(?P<end_time>{_TIME}))?)?)?$"
)
_DEFAULT_SWITCH_TIME = timedelta(hours=2)


def parse_posix_time(text: str) -> timedelta:
    """``-5:30`` -> -5 h 30 min; hours may exceed 24 in transition times."""
    sign = -1 if text.startswith("-") else 1
    parts = [int(part) for part in text.lstrip("+-").split(":")]
    parts += [0] * (3 - len(parts))
    return sign * timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])


@dataclass(frozen=True)
class PosixDate:
    """The day of a transition in a given year."""

    text: str

    def in_year(self, year: int) -> date:
        if self.text.startswith("M"):
            month, week, weekday_number = (int(part) for part in self.text[1:].split("."))
            weekday = Weekday((weekday_number - 1) % cm.DAYS_IN_WEEK)  # POSIX: 0 = Sunday
            found = cm.nth_weekday_of_month(year, month, weekday, -1 if week == 5 else week)
            if found is None:
                raise TimeZoneError(f"no week {week} in month {month} of {year}")
            return found
        if self.text.startswith("J"):
            number = int(self.text[1:])  # 1..365, February 29 is skipped
            if cm.is_leap_year(year) and number >= 60:
                number += 1
        else:
            number = int(self.text) + 1
        day = cm.date_from_day_of_year(year, number)
        if day is None:
            raise TimeZoneError(f"day {self.text} does not exist in {year}")
        return day


@dataclass(frozen=True)
class PosixZone:
    """A zone with a standard offset and, optionally, a yearly daylight period."""

    name: str
    standard: timedelta
    daylight: timedelta | None = None
    start: PosixDate | None = None
    start_time: timedelta = _DEFAULT_SWITCH_TIME
    end: PosixDate | None = None
    end_time: timedelta = _DEFAULT_SWITCH_TIME

    def switches(self, year: int) -> tuple[datetime, datetime] | None:
        """UTC instants when daylight time starts and ends in ``year``."""
        if self.daylight is None or self.start is None or self.end is None:
            return None
        # The start is given in standard local time, the end in daylight time.
        begin = datetime.combine(self.start.in_year(year), datetime.min.time()) + self.start_time
        finish = datetime.combine(self.end.in_year(year), datetime.min.time()) + self.end_time
        return (
            (begin - self.standard).replace(tzinfo=UTC),
            (finish - self.daylight).replace(tzinfo=UTC),
        )

    def offset_at(self, instant: datetime) -> timedelta:
        switches = self.switches(instant.year)
        if switches is None or self.daylight is None:
            return self.standard
        begin, finish = switches
        if begin < finish:  # northern hemisphere: daylight inside the year
            return self.daylight if begin <= instant < finish else self.standard
        # Southern hemisphere: daylight time spans New Year.
        return self.standard if finish <= instant < begin else self.daylight


def parse_posix_tz(name: str, text: str) -> PosixZone:
    """Parse a POSIX TZ string into a :class:`PosixZone` called ``name``."""
    match = _POSIX.match(text.strip())
    if match is None:
        raise TimeZoneError(f"malformed POSIX TZ string {text!r}", tzid=name)
    standard = -parse_posix_time(match["std_off"])
    if match["dst"] is None:
        return PosixZone(name, standard)
    daylight = (
        -parse_posix_time(match["dst_off"]) if match["dst_off"] else standard + timedelta(hours=1)
    )
    if match["start"] is None or match["end"] is None:
        raise TimeZoneError("daylight time needs start and end rules", tzid=name)
    return PosixZone(
        name,
        standard,
        daylight,
        PosixDate(match["start"]),
        parse_posix_time(match["start_time"]) if match["start_time"] else _DEFAULT_SWITCH_TIME,
        PosixDate(match["end"]),
        parse_posix_time(match["end_time"]) if match["end_time"] else _DEFAULT_SWITCH_TIME,
    )
