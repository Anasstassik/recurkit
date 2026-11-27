from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import date, datetime

from recurkit.errors import TimeZoneError
from recurkit.expand.defaults import ExpansionPlan, plan_for
from recurkit.expand.expanders import expand_period
from recurkit.expand.filters import DayFilter, limits_for
from recurkit.expand.periods import Period, iter_periods
from recurkit.expand.setpos import apply_set_pos
from recurkit.expand.subdaily import is_sub_daily, sub_daily_plan, sub_daily_values
from recurkit.expand.work import report_expanded_period
from recurkit.rule.model import Rule

type Occurrence = date | datetime
type ValidityCheck = Callable[[Occurrence], bool]


def require_floating(rule: Rule) -> None:
    if rule.tzid is not None:
        raise TimeZoneError(
            "expand works on local time only; expand a zoned rule through RecurrenceSet",
            tzid=rule.tzid,
        )


def _in_kind_of(dtstart: Occurrence, value: Occurrence) -> Occurrence:
    if not isinstance(dtstart, datetime):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, datetime):
        return value
    if dtstart.tzinfo is None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if dtstart.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=dtstart.tzinfo)
    return value


def effective_until(rule: Rule, horizon: Occurrence | None = None) -> Occurrence | None:
    dtstart = rule.require_dtstart()
    bounds = [_in_kind_of(dtstart, value) for value in (rule.until, horizon) if value is not None]
    return min(bounds) if bounds else None


def _bound_day(bound: Occurrence) -> date:
    return bound.date() if isinstance(bound, datetime) else bound


def period_occurrences(
    plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...]
) -> list[Occurrence]:
    report_expanded_period()
    days = expand_period(plan, period, limits)
    values = [value for day in days for value in plan.values_on(day)]
    return apply_set_pos(values, plan.by_set_pos)


def occurrences(
    rule: Rule,
    *,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Iterator[Occurrence]:
    require_floating(rule)
    return _generate(rule, is_valid, effective_until(rule, until))


def _day_values(plan: ExpansionPlan, bound: Occurrence | None) -> Iterator[Occurrence]:
    bound_day = _bound_day(bound) if bound is not None else None
    limits = limits_for(plan)
    for period in iter_periods(plan):
        if bound_day is not None and period.first > bound_day:
            return
        yield from period_occurrences(plan, period, limits)


def finish(
    values: Iterable[Occurrence],
    first: Occurrence,
    is_valid: ValidityCheck | None,
    bound: Occurrence | None,
    count: int | None,
) -> Iterator[Occurrence]:
    remaining = count
    for value in values:
        if value < first:
            continue
        if bound is not None and value > bound:
            return
        if is_valid is not None and not is_valid(value):
            continue
        yield value
        if remaining is not None:
            remaining -= 1
            if remaining == 0:
                return


def _generate(
    rule: Rule, is_valid: ValidityCheck | None, bound: Occurrence | None
) -> Iterator[Occurrence]:
    values: Iterable[Occurrence]
    if is_sub_daily(rule.freq):
        values = sub_daily_values(sub_daily_plan(rule), 0, bound)
    else:
        values = _day_values(plan_for(rule), bound)
    return finish(values, rule.require_dtstart(), is_valid, bound, rule.count)
