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
    index: int
    first: date
    last: date

    def __contains__(self, value: object) -> bool:
        return isinstance(value, date) and self.first <= value <= self.last

    @property
    def length(self) -> int:
        return cm.days_between(self.first, self.last) + 1

    def days(self) -> Iterator[date]:
        first = cm.date_to_ordinal(self.first)
        for ordinal in range(first, first + self.length):
            yield cm.date_from_ordinal(ordinal)


def period_start(freq: Frequency, value: date, wkst: Weekday = Weekday.MO) -> date:
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
    origin = period_start(plan.freq, plan.start, plan.wkst)
    index = step * plan.interval
    first = shift_period_start(plan.freq, origin, index)
    if first is None:
        return None
    try:
        last = period_last_day(plan.freq, first)
    except ValueError:
        last = date(cm.MAX_YEAR, 12, 31)
    return Period(index, first, last)


def iter_periods(plan: ExpansionPlan, first_step: int = 0) -> Iterator[Period]:
    step = first_step
    while (period := period_at(plan, step)) is not None:
        yield period
        step += 1


def step_containing(plan: ExpansionPlan, value: date) -> int:
    index = period_index(plan.freq, plan.start, value, plan.wkst)
    return index // plan.interval


def first_step_ending_at_or_after(plan: ExpansionPlan, value: date) -> int:
    step = step_containing(plan, value)
    period = period_at(plan, step)
    if period is not None and period.last < value:
        step += 1
    return max(step, 0)
