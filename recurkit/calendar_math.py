"""Proleptic Gregorian calendar arithmetic.

This module is the bottom layer of RecurKit: it imports nothing from the
library. Dates are handled as (year, month, day) integers or ``datetime.date``
values; ordinals follow the convention of ``date.toordinal()`` (0001-01-01 is
day 1) but are computed here from first principles.
"""

from __future__ import annotations

from datetime import date
from enum import IntEnum

MIN_YEAR = 1
MAX_YEAR = 9999
MONTHS_IN_YEAR = 12
DAYS_IN_WEEK = 7

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)

_WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

_DAYS_IN_400_YEARS = 146097
_DAYS_IN_100_YEARS = 36524
_DAYS_IN_4_YEARS = 1461
_DAYS_IN_COMMON_YEAR = 365


def check_year(year: int) -> None:
    """Raise ``ValueError`` unless ``year`` is in the supported range 1..9999."""
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"year {year} is out of range {MIN_YEAR}..{MAX_YEAR}")


def check_month(month: int) -> None:
    """Raise ``ValueError`` unless ``month`` is in 1..12."""
    if not 1 <= month <= MONTHS_IN_YEAR:
        raise ValueError(f"month {month} is out of range 1..{MONTHS_IN_YEAR}")


def is_leap_year(year: int) -> bool:
    """Gregorian rule: divisible by 4, except centuries not divisible by 400."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_year(year: int) -> int:
    return 366 if is_leap_year(year) else _DAYS_IN_COMMON_YEAR


def days_in_month(year: int, month: int) -> int:
    check_month(month)
    if month == 2 and is_leap_year(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def days_before_month(year: int, month: int) -> int:
    """Number of days in ``year`` before the first day of ``month``."""
    check_month(month)
    leap_day = 1 if month > 2 and is_leap_year(year) else 0
    return _DAYS_BEFORE_MONTH[month - 1] + leap_day


def days_before_year(year: int) -> int:
    """Number of days before January 1st of ``year`` since 0001-01-01."""
    y = year - 1
    return y * _DAYS_IN_COMMON_YEAR + y // 4 - y // 100 + y // 400


def is_valid_date(year: int, month: int, day: int) -> bool:
    """True if the triple names an existing day (e.g. not February 30)."""
    if not MIN_YEAR <= year <= MAX_YEAR or not 1 <= month <= MONTHS_IN_YEAR:
        return False
    return 1 <= day <= days_in_month(year, month)


def check_date(year: int, month: int, day: int) -> None:
    if not is_valid_date(year, month, day):
        raise ValueError(f"{year:04d}-{month:02d}-{day:02d} is not a valid date")


def ymd_to_ordinal(year: int, month: int, day: int) -> int:
    """Day number of the date, 0001-01-01 being day 1."""
    check_date(year, month, day)
    return days_before_year(year) + days_before_month(year, month) + day


def ordinal_to_ymd(ordinal: int) -> tuple[int, int, int]:
    """Inverse of :func:`ymd_to_ordinal`.

    The day number is split into whole 400-, 100-, 4- and 1-year cycles; the
    last year of a 100-year or 4-year cycle is the one that may be a leap year,
    so a remainder equal to a full cycle means "December 31st of that year".
    """
    if not 1 <= ordinal <= days_before_year(MAX_YEAR + 1):
        raise ValueError(f"ordinal {ordinal} is out of range")
    n = ordinal - 1
    n400, n = divmod(n, _DAYS_IN_400_YEARS)
    n100, n = divmod(n, _DAYS_IN_100_YEARS)
    n4, n = divmod(n, _DAYS_IN_4_YEARS)
    n1, n = divmod(n, _DAYS_IN_COMMON_YEAR)
    year = n400 * 400 + n100 * 100 + n4 * 4 + n1 + 1
    if n1 == 4 or n100 == 4:
        return year - 1, 12, 31
    month = _month_for_day_of_year(year, n + 1)
    return year, month, n + 1 - days_before_month(year, month)


def _month_for_day_of_year(year: int, day_of_year: int) -> int:
    month = (day_of_year + 50) >> 5
    if days_before_month(year, month) >= day_of_year:
        month -= 1
    return month


def date_to_ordinal(value: date) -> int:
    return ymd_to_ordinal(value.year, value.month, value.day)


def date_from_ordinal(ordinal: int) -> date:
    return date(*ordinal_to_ymd(ordinal))


def add_days(value: date, days: int) -> date:
    return date_from_ordinal(date_to_ordinal(value) + days)


def days_between(start: date, end: date) -> int:
    """Signed number of days from ``start`` to ``end``."""
    return date_to_ordinal(end) - date_to_ordinal(start)


def weekday_index(year: int, month: int, day: int) -> int:
    """Day of the week, Monday = 0 ... Sunday = 6 (0001-01-01 was a Monday)."""
    return (ymd_to_ordinal(year, month, day) - 1) % DAYS_IN_WEEK


def day_of_year(year: int, month: int, day: int) -> int:
    """1-based day number within the year (January 1st is 1)."""
    check_date(year, month, day)
    return days_before_month(year, month) + day


def date_from_day_of_year(year: int, number: int) -> date | None:
    """Date of the ``number``-th day of ``year``; negative counts from the end.

    Returns ``None`` when the year has no such day (e.g. day 366 of 2026).
    """
    check_year(year)
    total = days_in_year(year)
    if number < 0:
        number += total + 1
    if not 1 <= number <= total:
        return None
    return date_from_ordinal(days_before_year(year) + number)


def resolve_month_day(year: int, month: int, month_day: int) -> int | None:
    """Turn a BYMONTHDAY value into a day of the month.

    Negative values count from the end of the month (-1 is the last day).
    Returns ``None`` when the month has no such day: the 31st of a 30-day month
    is skipped, never moved to the 30th.
    """
    length = days_in_month(year, month)
    day = length + month_day + 1 if month_day < 0 else month_day
    if 1 <= day <= length:
        return day
    return None


class Weekday(IntEnum):
    """Day of the week with the numbering of ``date.weekday()`` (MO = 0)."""

    MO = 0
    TU = 1
    WE = 2
    TH = 3
    FR = 4
    SA = 5
    SU = 6

    @property
    def code(self) -> str:
        """Two-letter iCalendar code, e.g. ``"TU"``."""
        return _WEEKDAY_CODES[self.value]

    @classmethod
    def from_code(cls, code: str) -> Weekday:
        """Parse a two-letter iCalendar weekday code (case-insensitive)."""
        try:
            return cls(_WEEKDAY_CODES.index(code.upper()))
        except ValueError:
            raise ValueError(f"unknown weekday code: {code!r}") from None

    @classmethod
    def of(cls, value: date) -> Weekday:
        return cls(weekday_index(value.year, value.month, value.day))


def weekday_offset(weekday: Weekday, week_start: Weekday) -> int:
    """Position of ``weekday`` in a week that begins on ``week_start`` (0..6)."""
    return (weekday - week_start) % DAYS_IN_WEEK


def week_start(value: date, wkst: Weekday = Weekday.MO) -> date:
    """First day of the week that contains ``value``, weeks starting on ``wkst``."""
    return add_days(value, -weekday_offset(Weekday.of(value), wkst))


def first_weekday_on_or_after(value: date, weekday: Weekday) -> date:
    return add_days(value, (weekday - Weekday.of(value)) % DAYS_IN_WEEK)


def last_weekday_on_or_before(value: date, weekday: Weekday) -> date:
    return add_days(value, -((Weekday.of(value) - weekday) % DAYS_IN_WEEK))


def _nth_weekday_in_range(first: date, last: date, weekday: Weekday, n: int) -> date | None:
    """The ``n``-th ``weekday`` between ``first`` and ``last`` inclusive.

    Positive ``n`` counts from ``first``, negative from ``last`` (-1 is the
    last such weekday). ``None`` if the range has fewer than ``|n|`` of them.
    """
    if n == 0:
        raise ValueError("weekday ordinal must not be zero")
    # Work with ordinals so that a far ordinal near year 9999 is rejected
    # before a date outside the supported range is ever built.
    if n > 0:
        ordinal = (
            date_to_ordinal(first_weekday_on_or_after(first, weekday)) + (n - 1) * DAYS_IN_WEEK
        )
        return date_from_ordinal(ordinal) if ordinal <= date_to_ordinal(last) else None
    ordinal = date_to_ordinal(last_weekday_on_or_before(last, weekday)) + (n + 1) * DAYS_IN_WEEK
    return date_from_ordinal(ordinal) if ordinal >= date_to_ordinal(first) else None


def nth_weekday_of_month(year: int, month: int, weekday: Weekday, n: int) -> date | None:
    """E.g. ``2TU`` (second Tuesday) or ``-1FR`` (last Friday) of a month.

    Returns ``None`` when the month has no such day, e.g. a 5th Monday.
    """
    first = date(year, month, 1)
    last = date(year, month, days_in_month(year, month))
    return _nth_weekday_in_range(first, last, weekday, n)


def nth_weekday_of_year(year: int, weekday: Weekday, n: int) -> date | None:
    """E.g. ``20MO`` (20th Monday of the year) or ``-1SU`` (last Sunday)."""
    check_year(year)
    return _nth_weekday_in_range(date(year, 1, 1), date(year, 12, 31), weekday, n)


def weekdays_of_month(year: int, month: int, weekday: Weekday) -> list[date]:
    """All days of the month that fall on ``weekday``, in order."""
    last = days_in_month(year, month)
    day = first_weekday_on_or_after(date(year, month, 1), weekday).day
    return [date(year, month, d) for d in range(day, last + 1, DAYS_IN_WEEK)]


def weekdays_of_year(year: int, weekday: Weekday) -> list[date]:
    """All days of the year that fall on ``weekday``, in order."""
    first = date_to_ordinal(first_weekday_on_or_after(date(year, 1, 1), weekday))
    last = days_before_year(year) + days_in_year(year)
    return [date_from_ordinal(o) for o in range(first, last + 1, DAYS_IN_WEEK)]


def weekday_ordinals_in_month(value: date) -> tuple[int, int]:
    """Positive and negative ordinal of ``value`` among same weekdays of its month.

    The last Friday of a month with five Fridays is ``(5, -1)``.
    """
    length = days_in_month(value.year, value.month)
    positive = (value.day - 1) // DAYS_IN_WEEK + 1
    negative = -((length - value.day) // DAYS_IN_WEEK + 1)
    return positive, negative


def weekday_ordinals_in_year(value: date) -> tuple[int, int]:
    """Positive and negative ordinal of ``value`` among same weekdays of its year."""
    number = day_of_year(value.year, value.month, value.day)
    positive = (number - 1) // DAYS_IN_WEEK + 1
    negative = -((days_in_year(value.year) - number) // DAYS_IN_WEEK + 1)
    return positive, negative


def month_index(year: int, month: int) -> int:
    """Number of months since January of year 0; makes months comparable."""
    check_month(month)
    return year * MONTHS_IN_YEAR + (month - 1)


def month_from_index(index: int) -> tuple[int, int]:
    year, month0 = divmod(index, MONTHS_IN_YEAR)
    check_year(year)
    return year, month0 + 1


def months_between(start: date, end: date) -> int:
    """Signed number of calendar-month boundaries from ``start`` to ``end``.

    Only year and month matter: 31.01 -> 01.02 is one month.
    """
    return month_index(end.year, end.month) - month_index(start.year, start.month)


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """Shift a (year, month) pair by ``months`` (may be negative)."""
    return month_from_index(month_index(year, month) + months)


def years_between(start: date, end: date) -> int:
    return end.year - start.year


def weeks_between(start: date, end: date, wkst: Weekday = Weekday.MO) -> int:
    """Signed number of week boundaries from ``start`` to ``end``.

    Weeks begin on ``wkst``; two days of the same week give 0. With WKST=SU a
    Sunday and the following Monday are in the same week, with WKST=MO they are
    one week apart.
    """
    delta = days_between(week_start(start, wkst), week_start(end, wkst))
    return delta // DAYS_IN_WEEK


def add_weeks(value: date, weeks: int) -> date:
    return add_days(value, weeks * DAYS_IN_WEEK)


def ceil_div(numerator: int, denominator: int) -> int:
    """Ceiling division for a positive denominator: smallest q with q*d >= n."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return -(-numerator // denominator)


def next_multiple_at_or_after(value: int, step: int) -> int:
    """Smallest multiple of ``step`` that is >= ``value`` (``step`` > 0)."""
    return ceil_div(value, step) * step
