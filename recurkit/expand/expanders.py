from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from recurkit import calendar_math as cm
from recurkit.expand.defaults import ExpansionPlan
from recurkit.expand.filters import (
    DayFilter,
    apply_limits,
    limits_for,
    month_day_matches,
    month_matches,
    ordinal_scope,
    week_no_matches,
    weekday_matches,
    year_day_matches,
)
from recurkit.expand.periods import Period
from recurkit.rule.model import Frequency

ALL_MONTHS = tuple(range(1, cm.MONTHS_IN_YEAR + 1))


def _sorted_unique(days: Iterable[date]) -> list[date]:
    return sorted(set(days))


def month_days(plan: ExpansionPlan, year: int, month: int) -> list[date]:
    days = []
    for value in plan.by_month_day:
        day = cm.resolve_month_day(year, month, value)
        if day is not None:
            days.append(date(year, month, day))
    return days


def weekdays_in_month(plan: ExpansionPlan, year: int, month: int) -> list[date]:
    days: list[date] = []
    for weekday in plan.weekdays:
        days.extend(cm.weekdays_of_month(year, month, weekday))
    for item in plan.nth_weekdays:
        nth = cm.nth_weekday_of_month(year, month, item.weekday, item.n) if item.n else None
        if nth is not None:
            days.append(nth)
    return days


def weekdays_in_year(plan: ExpansionPlan, year: int) -> list[date]:
    days: list[date] = []
    for weekday in plan.weekdays:
        days.extend(cm.weekdays_of_year(year, weekday))
    for item in plan.nth_weekdays:
        nth = cm.nth_weekday_of_year(year, item.weekday, item.n) if item.n else None
        if nth is not None:
            days.append(nth)
    return days


def expand_monthly(
    plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]
) -> list[date]:
    year, month = period.first.year, period.first.month
    if plan.by_month and month not in plan.by_month:
        return []
    if plan.by_month_day:
        candidates = month_days(plan, year, month)
    else:
        candidates = weekdays_in_month(plan, year, month)
    return _sorted_unique(apply_limits(candidates, limits))


def expand_yearly(plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]) -> list[date]:
    year = period.first.year
    if plan.by_week_no or plan.by_year_day:
        return expand_yearly_by_numbers(plan, year)
    months = sorted(plan.by_month) if plan.by_month else ALL_MONTHS
    candidates: list[date] = []
    if plan.by_month_day:
        for month in months:
            candidates.extend(month_days(plan, year, month))
    elif plan.by_month:
        for month in months:
            candidates.extend(weekdays_in_month(plan, year, month))
    else:
        candidates = weekdays_in_year(plan, year)
    return _sorted_unique(apply_limits(candidates, limits))


def expand_yearly_by_numbers(plan: ExpansionPlan, year: int) -> list[date]:
    scope = ordinal_scope(plan)
    numbering = cm.WeekNumbering.for_year(year, plan.wkst)
    result = []
    for ordinal in range(cm.days_before_year(year) + 1, cm.days_before_year(year + 1) + 1):
        day = cm.date_from_ordinal(ordinal)
        if (
            month_matches(day, plan.by_month)
            and week_no_matches(day, plan.by_week_no, plan.wkst, numbering)
            and year_day_matches(day, plan.by_year_day)
            and month_day_matches(day, plan.by_month_day)
            and weekday_matches(day, plan.weekdays, plan.nth_weekdays, scope)
        ):
            result.append(day)
    return result


def expand_weekly(plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]) -> list[date]:
    first_weekday = cm.Weekday.of(period.first)
    offsets = (cm.weekday_offset(weekday, first_weekday) for weekday in plan.weekdays)
    candidates = [cm.add_days(period.first, offset) for offset in offsets if offset < period.length]
    return _sorted_unique(apply_limits(candidates, limits))


def expand_daily(plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]) -> list[date]:
    return apply_limits([period.first], limits)


def expand_period(
    plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...] | None = None
) -> list[date]:
    if limits is None:
        limits = limits_for(plan)
    match plan.freq:
        case Frequency.YEARLY:
            return expand_yearly(plan, period, limits)
        case Frequency.MONTHLY:
            return expand_monthly(plan, period, limits)
        case Frequency.WEEKLY:
            return expand_weekly(plan, period, limits)
        case Frequency.DAILY:
            return expand_daily(plan, period, limits)
