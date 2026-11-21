from __future__ import annotations

from dataclasses import dataclass
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
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"year {year} is out of range {MIN_YEAR}..{MAX_YEAR}")


def check_month(month: int) -> None:
    if not 1 <= month <= MONTHS_IN_YEAR:
        raise ValueError(f"month {month} is out of range 1..{MONTHS_IN_YEAR}")


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_year(year: int) -> int:
    return 366 if is_leap_year(year) else _DAYS_IN_COMMON_YEAR


def days_in_month(year: int, month: int) -> int:
    check_month(month)
    if month == 2 and is_leap_year(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def days_before_month(year: int, month: int) -> int:
    check_month(month)
    leap_day = 1 if month > 2 and is_leap_year(year) else 0
    return _DAYS_BEFORE_MONTH[month - 1] + leap_day


def days_before_year(year: int) -> int:
    y = year - 1
    return y * _DAYS_IN_COMMON_YEAR + y // 4 - y // 100 + y // 400


def is_valid_date(year: int, month: int, day: int) -> bool:
    if not MIN_YEAR <= year <= MAX_YEAR or not 1 <= month <= MONTHS_IN_YEAR:
        return False
    return 1 <= day <= days_in_month(year, month)


def check_date(year: int, month: int, day: int) -> None:
    if not is_valid_date(year, month, day):
        raise ValueError(f"{year:04d}-{month:02d}-{day:02d} is not a valid date")


def ymd_to_ordinal(year: int, month: int, day: int) -> int:
    check_date(year, month, day)
    return days_before_year(year) + days_before_month(year, month) + day


def ordinal_to_ymd(ordinal: int) -> tuple[int, int, int]:
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
    return date_to_ordinal(end) - date_to_ordinal(start)


def weekday_index(year: int, month: int, day: int) -> int:
    return (ymd_to_ordinal(year, month, day) - 1) % DAYS_IN_WEEK


def day_of_year(year: int, month: int, day: int) -> int:
    check_date(year, month, day)
    return days_before_month(year, month) + day


def date_from_day_of_year(year: int, number: int) -> date | None:
    check_year(year)
    total = days_in_year(year)
    if number < 0:
        number += total + 1
    if not 1 <= number <= total:
        return None
    return date_from_ordinal(days_before_year(year) + number)


def resolve_month_day(year: int, month: int, month_day: int) -> int | None:
    length = days_in_month(year, month)
    day = length + month_day + 1 if month_day < 0 else month_day
    if 1 <= day <= length:
        return day
    return None


class Weekday(IntEnum):
    MO = 0
    TU = 1
    WE = 2
    TH = 3
    FR = 4
    SA = 5
    SU = 6

    @property
    def code(self) -> str:
        return _WEEKDAY_CODES[self.value]

    @classmethod
    def from_code(cls, code: str) -> Weekday:
        try:
            return cls(_WEEKDAY_CODES.index(code.upper()))
        except ValueError:
            raise ValueError(f"unknown weekday code: {code!r}") from None

    @classmethod
    def of(cls, value: date) -> Weekday:
        return cls(weekday_index(value.year, value.month, value.day))


def weekday_offset(weekday: Weekday, week_start: Weekday) -> int:
    return (weekday - week_start) % DAYS_IN_WEEK


def week_start(value: date, wkst: Weekday = Weekday.MO) -> date:
    return add_days(value, -weekday_offset(Weekday.of(value), wkst))


def first_weekday_on_or_after(value: date, weekday: Weekday) -> date:
    return add_days(value, (weekday - Weekday.of(value)) % DAYS_IN_WEEK)


def last_weekday_on_or_before(value: date, weekday: Weekday) -> date:
    return add_days(value, -((Weekday.of(value) - weekday) % DAYS_IN_WEEK))


def _nth_weekday_in_range(first: date, last: date, weekday: Weekday, n: int) -> date | None:
    if n == 0:
        raise ValueError("weekday ordinal must not be zero")
    if n > 0:
        ordinal = (
            date_to_ordinal(first_weekday_on_or_after(first, weekday)) + (n - 1) * DAYS_IN_WEEK
        )
        return date_from_ordinal(ordinal) if ordinal <= date_to_ordinal(last) else None
    ordinal = date_to_ordinal(last_weekday_on_or_before(last, weekday)) + (n + 1) * DAYS_IN_WEEK
    return date_from_ordinal(ordinal) if ordinal >= date_to_ordinal(first) else None


def nth_weekday_of_month(year: int, month: int, weekday: Weekday, n: int) -> date | None:
    first = date(year, month, 1)
    last = date(year, month, days_in_month(year, month))
    return _nth_weekday_in_range(first, last, weekday, n)


def nth_weekday_of_year(year: int, weekday: Weekday, n: int) -> date | None:
    check_year(year)
    return _nth_weekday_in_range(date(year, 1, 1), date(year, 12, 31), weekday, n)


def weekdays_of_month(year: int, month: int, weekday: Weekday) -> list[date]:
    last = days_in_month(year, month)
    day = first_weekday_on_or_after(date(year, month, 1), weekday).day
    return [date(year, month, d) for d in range(day, last + 1, DAYS_IN_WEEK)]


def weekdays_of_year(year: int, weekday: Weekday) -> list[date]:
    first = date_to_ordinal(first_weekday_on_or_after(date(year, 1, 1), weekday))
    last = days_before_year(year) + days_in_year(year)
    return [date_from_ordinal(o) for o in range(first, last + 1, DAYS_IN_WEEK)]


def weekday_ordinals_in_month(value: date) -> tuple[int, int]:
    length = days_in_month(value.year, value.month)
    positive = (value.day - 1) // DAYS_IN_WEEK + 1
    negative = -((length - value.day) // DAYS_IN_WEEK + 1)
    return positive, negative


def weekday_ordinals_in_year(value: date) -> tuple[int, int]:
    number = day_of_year(value.year, value.month, value.day)
    positive = (number - 1) // DAYS_IN_WEEK + 1
    negative = -((days_in_year(value.year) - number) // DAYS_IN_WEEK + 1)
    return positive, negative


def month_index(year: int, month: int) -> int:
    check_month(month)
    return year * MONTHS_IN_YEAR + (month - 1)


def month_from_index(index: int) -> tuple[int, int]:
    year, month0 = divmod(index, MONTHS_IN_YEAR)
    check_year(year)
    return year, month0 + 1


def months_between(start: date, end: date) -> int:
    return month_index(end.year, end.month) - month_index(start.year, start.month)


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    return month_from_index(month_index(year, month) + months)


def years_between(start: date, end: date) -> int:
    return end.year - start.year


def weeks_between(start: date, end: date, wkst: Weekday = Weekday.MO) -> int:
    delta = days_between(week_start(start, wkst), week_start(end, wkst))
    return delta // DAYS_IN_WEEK


def add_weeks(value: date, weeks: int) -> date:
    return add_days(value, weeks * DAYS_IN_WEEK)


def ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return -(-numerator // denominator)


def next_multiple_at_or_after(value: int, step: int) -> int:
    return ceil_div(value, step) * step


def first_week_start(year: int, wkst: Weekday = Weekday.MO) -> date:
    check_year(year)
    return date_from_ordinal(_week_start_ordinal(year, wkst))


@dataclass(frozen=True)
class WeekNumbering:
    year: int
    previous_start: int
    start: int
    next_start: int
    following_start: int

    @classmethod
    def for_year(cls, year: int, wkst: Weekday = Weekday.MO) -> WeekNumbering:
        check_year(year)
        starts = [_week_start_ordinal(y, wkst) for y in (year - 1, year, year + 1, year + 2)]
        return cls(year, *starts)

    @property
    def weeks(self) -> int:
        return (self.next_start - self.start) // DAYS_IN_WEEK

    def of(self, value: date) -> tuple[int, int, int]:
        ordinal = date_to_ordinal(value)
        if ordinal < self.start:
            year, first, last = self.year - 1, self.previous_start, self.start
        elif ordinal >= self.next_start:
            year, first, last = self.year + 1, self.next_start, self.following_start
        else:
            year, first, last = self.year, self.start, self.next_start
        week = (ordinal - first) // DAYS_IN_WEEK + 1
        return year, week, (last - first) // DAYS_IN_WEEK


def _week_start_ordinal(year: int, wkst: Weekday) -> int:
    jan1 = days_before_year(year) + 1
    offset = ((jan1 - 1) % DAYS_IN_WEEK - wkst) % DAYS_IN_WEEK
    return jan1 - offset if DAYS_IN_WEEK - offset >= 4 else jan1 + DAYS_IN_WEEK - offset


def week_number(value: date, wkst: Weekday = Weekday.MO) -> tuple[int, int, int]:
    return WeekNumbering.for_year(value.year, wkst).of(value)
