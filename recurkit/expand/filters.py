"""Limit filters: the "Limit" cells of the BYxxx table in RFC 5545, 3.3.10.

A limit rule part removes candidate days instead of producing new ones,
e.g. ``FREQ=DAILY;BYMONTH=1`` keeps only January days. Which parts limit
depends on FREQ (RRULE-19):

========== ====== ====== ======= ======
part       DAILY  WEEKLY MONTHLY YEARLY
========== ====== ====== ======= ======
BYMONTH    limit  limit  limit   expand
BYMONTHDAY limit  n/a    expand  expand
BYDAY      limit  expand note 1  note 2
========== ====== ====== ======= ======

Note 1/2: BYDAY limits MONTHLY and YEARLY when BYMONTHDAY is present.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from enum import Enum

from recurkit import calendar_math as cm
from recurkit.calendar_math import Weekday
from recurkit.expand.defaults import ExpansionPlan
from recurkit.rule.model import Frequency, WeekdayNum

type DayFilter = Callable[[date], bool]


class OrdinalScope(Enum):
    """What a numeric BYDAY counts within: the month or the whole year (RRULE-20)."""

    MONTH = "month"
    YEAR = "year"


def ordinal_scope(plan: ExpansionPlan) -> OrdinalScope:
    """YEARLY without BYMONTH counts weekdays in the year; everything else in the month."""
    if plan.freq is Frequency.YEARLY and not plan.by_month:
        return OrdinalScope.YEAR
    return OrdinalScope.MONTH


def month_matches(day: date, by_month: frozenset[int]) -> bool:
    return not by_month or day.month in by_month


def month_day_matches(day: date, by_month_day: tuple[int, ...]) -> bool:
    """True if ``day`` is one of the BYMONTHDAY values; negatives count from month end."""
    if not by_month_day:
        return True
    length = cm.days_in_month(day.year, day.month)
    negative = day.day - length - 1
    return day.day in by_month_day or negative in by_month_day


def weekday_matches(
    day: date,
    weekdays: frozenset[Weekday],
    nth_weekdays: tuple[WeekdayNum, ...],
    scope: OrdinalScope = OrdinalScope.MONTH,
) -> bool:
    """True if ``day`` matches a plain BYDAY value or a numeric one within ``scope``."""
    if not weekdays and not nth_weekdays:
        return True
    weekday = Weekday.of(day)
    if weekday in weekdays:
        return True
    if not nth_weekdays:
        return False
    if scope is OrdinalScope.MONTH:
        positive, negative = cm.weekday_ordinals_in_month(day)
    else:
        positive, negative = cm.weekday_ordinals_in_year(day)
    return any(item.weekday is weekday and item.n in (positive, negative) for item in nth_weekdays)


def limits_for(plan: ExpansionPlan) -> tuple[DayFilter, ...]:
    """The limit filters that apply to the plan's frequency, in RFC order."""
    filters: list[DayFilter] = []
    freq = plan.freq
    if plan.by_month and freq is not Frequency.YEARLY:
        filters.append(lambda day: month_matches(day, plan.by_month))
    if plan.by_month_day and freq is Frequency.DAILY:
        filters.append(lambda day: month_day_matches(day, plan.by_month_day))
    by_day_limits = freq is Frequency.DAILY or (
        freq in (Frequency.MONTHLY, Frequency.YEARLY) and bool(plan.by_month_day)
    )
    if plan.has_by_day and by_day_limits:
        scope = ordinal_scope(plan)
        filters.append(lambda day: weekday_matches(day, plan.weekdays, plan.nth_weekdays, scope))
    return tuple(filters)


def apply_limits(days: Iterable[date], filters: tuple[DayFilter, ...]) -> list[date]:
    """Keep the days that pass every filter, preserving order."""
    return [day for day in days if all(check(day) for check in filters)]
