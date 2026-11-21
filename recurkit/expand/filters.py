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
    MONTH = "month"
    YEAR = "year"


def ordinal_scope(plan: ExpansionPlan) -> OrdinalScope:
    if plan.freq is Frequency.YEARLY and not plan.by_month:
        return OrdinalScope.YEAR
    return OrdinalScope.MONTH


def month_matches(day: date, by_month: frozenset[int]) -> bool:
    return not by_month or day.month in by_month


def month_day_matches(day: date, by_month_day: tuple[int, ...]) -> bool:
    if not by_month_day:
        return True
    length = cm.days_in_month(day.year, day.month)
    negative = day.day - length - 1
    return day.day in by_month_day or negative in by_month_day


def year_day_matches(day: date, by_year_day: tuple[int, ...]) -> bool:
    if not by_year_day:
        return True
    number = cm.day_of_year(day.year, day.month, day.day)
    return number in by_year_day or number - cm.days_in_year(day.year) - 1 in by_year_day


def week_no_matches(
    day: date,
    by_week_no: tuple[int, ...],
    wkst: Weekday,
    numbering: cm.WeekNumbering | None = None,
) -> bool:
    if not by_week_no:
        return True
    if numbering is None:
        numbering = cm.WeekNumbering.for_year(day.year, wkst)
    _, week, total = numbering.of(day)
    return week in by_week_no or week - total - 1 in by_week_no


def weekday_matches(
    day: date,
    weekdays: frozenset[Weekday],
    nth_weekdays: tuple[WeekdayNum, ...],
    scope: OrdinalScope = OrdinalScope.MONTH,
) -> bool:
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
    return [day for day in days if all(check(day) for check in filters)]
