"""Expanders: the candidate days of one period, the "Expand" cells of RFC 5545, 3.3.10.

Each expander returns the sorted, de-duplicated days of a period that the
rule's BYxxx parts select, before BYSETPOS, COUNT and UNTIL are applied.
Days that do not exist (February 30, the 31st of a 30-day month, a fifth
Monday) are never produced, so they are neither emitted nor counted
(RRULE-16).
"""

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
    """BYMONTHDAY values of the plan resolved in one month; missing days are skipped."""
    days = []
    for value in plan.by_month_day:
        day = cm.resolve_month_day(year, month, value)
        if day is not None:
            days.append(date(year, month, day))
    return days


def weekdays_in_month(plan: ExpansionPlan, year: int, month: int) -> list[date]:
    """Days of a month selected by BYDAY: every MO for ``MO``, one day for ``2TU``."""
    days: list[date] = []
    for weekday in plan.weekdays:
        days.extend(cm.weekdays_of_month(year, month, weekday))
    for item in plan.nth_weekdays:
        nth = cm.nth_weekday_of_month(year, month, item.weekday, item.n) if item.n else None
        if nth is not None:
            days.append(nth)
    return days


def weekdays_in_year(plan: ExpansionPlan, year: int) -> list[date]:
    """Days of a year selected by BYDAY, numeric values counted within the year."""
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
    """Candidates of a MONTHLY period.

    BYMONTH limits the month; BYMONTHDAY expands, and BYDAY expands only
    when BYMONTHDAY is absent (note 1 of the table), otherwise it limits.
    """
    year, month = period.first.year, period.first.month
    if plan.by_month and month not in plan.by_month:
        return []
    if plan.by_month_day:
        candidates = month_days(plan, year, month)
    else:
        candidates = weekdays_in_month(plan, year, month)
    return _sorted_unique(apply_limits(candidates, limits))


def expand_yearly(plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]) -> list[date]:
    """Candidates of a YEARLY period.

    BYMONTH expands to the listed months (all months when absent). Then
    BYMONTHDAY expands within each month; without BYMONTHDAY, BYDAY expands
    within each listed month, or within the whole year when BYMONTH is
    absent (note 2 of the table, RRULE-20).
    """
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
    """YEARLY candidates when BYWEEKNO or BYYEARDAY is present.

    Every part then selects days of the year, so the candidates are the days
    of the year that pass all present parts in the RFC order BYMONTH,
    BYWEEKNO, BYYEARDAY, BYMONTHDAY, BYDAY. BYDAY is counted within the
    month when BYMONTH is present (RRULE-20); with BYWEEKNO it can only be a
    plain weekday (RRULE-25), which selects those days of the listed weeks.
    """
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
    """Candidates of a WEEKLY period: the BYDAY weekdays of the week.

    The week starts on WKST, which decides which days belong to the same
    period when INTERVAL > 1 (RRULE-21). BYMONTH limits the days, so a week
    that straddles two months may keep only part of its days.
    """
    offsets = (cm.weekday_offset(weekday, plan.wkst) for weekday in plan.weekdays)
    # The last week of year 9999 is cut short: skip days past the period end.
    candidates = [cm.add_days(period.first, offset) for offset in offsets if offset < period.length]
    return _sorted_unique(apply_limits(candidates, limits))


def expand_daily(plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]) -> list[date]:
    """Candidates of a DAILY period: the day itself if every limit lets it through."""
    return apply_limits([period.first], limits)


def expand_period(
    plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...] | None = None
) -> list[date]:
    """Candidate days of ``period`` for the plan's frequency.

    ``limits`` can be precomputed with :func:`limits_for` when many periods of
    the same plan are expanded.
    """
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
