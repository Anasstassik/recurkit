"""Periods of a rule: the years, months, weeks or days stepped by FREQ and INTERVAL.

Periods are counted from the period that contains DTSTART, not from
January 1st: ``FREQ=MONTHLY;INTERVAL=2`` starting in March gives March,
May, July... A WEEKLY period starts on the WKST weekday (RRULE-21).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from recurkit import calendar_math as cm
from recurkit.calendar_math import Weekday
from recurkit.expand.defaults import ExpansionPlan
from recurkit.rule.model import Frequency


@dataclass(frozen=True)
class Period:
    """One period of a rule.

    ``index`` is the number of base periods (years, months, weeks, days) from
    the DTSTART period; for a rule with INTERVAL=k it is a multiple of k.
    ``first`` and ``last`` are inclusive.
    """

    index: int
    first: date
    last: date

    def __contains__(self, value: object) -> bool:
        return isinstance(value, date) and self.first <= value <= self.last

    @property
    def length(self) -> int:
        return cm.days_between(self.first, self.last) + 1

    def days(self) -> Iterator[date]:
        """All days of the period in order."""
        first = cm.date_to_ordinal(self.first)
        for ordinal in range(first, first + self.length):
            yield cm.date_from_ordinal(ordinal)


def period_start(freq: Frequency, value: date, wkst: Weekday = Weekday.MO) -> date:
    """First day of the base period of ``freq`` that contains ``value``."""
    match freq:
        case Frequency.YEARLY:
            return date(value.year, 1, 1)
        case Frequency.MONTHLY:
            return date(value.year, value.month, 1)
        case Frequency.WEEKLY:
            return cm.week_start(value, wkst)
        case Frequency.DAILY:
            return value


def period_last_day(freq: Frequency, start: date) -> date:
    """Last day of the base period that begins on ``start``."""
    match freq:
        case Frequency.YEARLY:
            return date(start.year, 12, 31)
        case Frequency.MONTHLY:
            return date(start.year, start.month, cm.days_in_month(start.year, start.month))
        case Frequency.WEEKLY:
            return cm.add_days(start, cm.DAYS_IN_WEEK - 1)
        case Frequency.DAILY:
            return start


def shift_period_start(freq: Frequency, start: date, count: int) -> date | None:
    """Start of the base period ``count`` periods after the one starting on ``start``.

    Returns ``None`` when the result falls outside years 1..9999.
    """
    try:
        match freq:
            case Frequency.YEARLY:
                year = start.year + count
                cm.check_year(year)
                return date(year, 1, 1)
            case Frequency.MONTHLY:
                year, month = cm.add_months(start.year, start.month, count)
                return date(year, month, 1)
            case Frequency.WEEKLY:
                return cm.add_weeks(start, count)
            case Frequency.DAILY:
                return cm.add_days(start, count)
    except ValueError:
        return None


def period_index(freq: Frequency, origin: date, value: date, wkst: Weekday = Weekday.MO) -> int:
    """Signed number of base periods from the period of ``origin`` to that of ``value``."""
    match freq:
        case Frequency.YEARLY:
            return cm.years_between(origin, value)
        case Frequency.MONTHLY:
            return cm.months_between(origin, value)
        case Frequency.WEEKLY:
            return cm.weeks_between(origin, value, wkst)
        case Frequency.DAILY:
            return cm.days_between(origin, value)


def period_at(plan: ExpansionPlan, step: int) -> Period | None:
    """The ``step``-th period of the rule (step 0 contains DTSTART).

    ``None`` if the period lies beyond the supported date range.
    """
    origin = period_start(plan.freq, plan.start, plan.wkst)
    index = step * plan.interval
    first = shift_period_start(plan.freq, origin, index)
    if first is None:
        return None
    try:
        last = period_last_day(plan.freq, first)
    except ValueError:  # the last week of year 9999 runs past December 31st
        last = date(cm.MAX_YEAR, 12, 31)
    return Period(index, first, last)


def iter_periods(plan: ExpansionPlan, first_step: int = 0) -> Iterator[Period]:
    """Periods of the rule from ``first_step`` on, until the end of year 9999."""
    step = first_step
    while (period := period_at(plan, step)) is not None:
        yield period
        step += 1


def step_containing(plan: ExpansionPlan, value: date) -> int:
    """Step of the rule period that contains ``value``, or the last step before it.

    Days between two periods of an INTERVAL > 1 rule (e.g. the odd weeks of a
    bi-weekly rule) belong to the preceding step. Negative before DTSTART.
    """
    index = period_index(plan.freq, plan.start, value, plan.wkst)
    return index // plan.interval


def first_step_ending_at_or_after(plan: ExpansionPlan, value: date) -> int:
    """Smallest step whose period ends on or after ``value`` (never negative).

    Used to jump straight to the period of a query window instead of walking
    all periods from DTSTART.
    """
    step = step_containing(plan, value)
    period = period_at(plan, step)
    if period is not None and period.last < value:
        step += 1
    return max(step, 0)
