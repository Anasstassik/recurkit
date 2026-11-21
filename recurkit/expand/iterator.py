from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime

from recurkit.expand.defaults import ExpansionPlan, plan_for
from recurkit.expand.expanders import expand_period
from recurkit.expand.filters import DayFilter, limits_for
from recurkit.expand.periods import Period, iter_periods
from recurkit.expand.setpos import apply_set_pos
from recurkit.rule.model import Rule

type Occurrence = date | datetime
type ValidityCheck = Callable[[Occurrence], bool]


def effective_until(rule: Rule, override: Occurrence | None = None) -> Occurrence | None:
    until = override if override is not None else rule.until
    if until is None:
        return None
    dtstart = rule.require_dtstart()
    if isinstance(until, datetime) and isinstance(dtstart, datetime):
        if dtstart.tzinfo is None and until.tzinfo is not None:
            return until.replace(tzinfo=None)
        if dtstart.tzinfo is not None and until.tzinfo is None:
            return until.replace(tzinfo=dtstart.tzinfo)
    return until


def _bound_day(bound: Occurrence) -> date:
    return bound.date() if isinstance(bound, datetime) else bound


def period_occurrences(
    plan: ExpansionPlan, period: Period, limits: tuple[DayFilter, ...] | None = None
) -> list[date]:
    return apply_set_pos(expand_period(plan, period, limits), plan.by_set_pos)


def occurrences(
    rule: Rule,
    *,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Iterator[Occurrence]:
    plan = plan_for(rule)
    bound = effective_until(rule, until)
    bound_day = _bound_day(bound) if bound is not None else None
    remaining = rule.count
    limits = limits_for(plan)
    for period in iter_periods(plan):
        if bound_day is not None and period.first > bound_day:
            return
        for day in period_occurrences(plan, period, limits):
            if day < plan.start:
                continue
            value = plan.combine(day)
            if bound is not None and value > bound:
                return
            if is_valid is not None and not is_valid(value):
                continue
            yield value
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    return
