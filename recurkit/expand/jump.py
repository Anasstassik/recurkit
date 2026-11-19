"""Arithmetic jumps over periods for ``between`` and ``after``.

Walking every period from DTSTART makes a query far in the future linear in
the distance. Without COUNT the occurrences of a period do not depend on the
periods before it, so a query can start at the period that contains the
window: its step is computed with month/week/day arithmetic (``periods``).
With COUNT, every earlier occurrence has to be counted, so the caller falls
back to the plain iterator.

Periods that a BYMONTH limit empties (``FREQ=DAILY;BYMONTH=12`` in March) are
skipped the same way: straight to the first period that touches an allowed
month.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime

from recurkit import calendar_math as cm
from recurkit.expand.defaults import ExpansionPlan, plan_for
from recurkit.expand.filters import limits_for
from recurkit.expand.iterator import (
    Occurrence,
    ValidityCheck,
    effective_until,
    occurrences,
    period_occurrences,
)
from recurkit.expand.periods import Period, first_step_ending_at_or_after, period_at
from recurkit.rule.model import Frequency, Rule


def can_jump(rule: Rule) -> bool:
    """Jumping is exact only when no occurrence before the window must be counted."""
    return rule.count is None


def _months_of(period: Period) -> set[int]:
    if period.first.year != period.last.year:
        return {period.first.month, period.last.month}
    return set(range(period.first.month, period.last.month + 1))


def next_allowed_month_start(after_day: date, by_month: frozenset[int]) -> date | None:
    """First day of the first month after the month of ``after_day`` listed in ``by_month``."""
    year, month = after_day.year, after_day.month
    for _ in range(cm.MONTHS_IN_YEAR):
        if year == cm.MAX_YEAR and month == cm.MONTHS_IN_YEAR:
            return None
        year, month = cm.add_months(year, month, 1)
        if month in by_month:
            return date(year, month, 1)
    return None


def next_productive_step(plan: ExpansionPlan, step: int, limit: date | None = None) -> int | None:
    """Smallest step >= ``step`` whose period is not emptied by a BYMONTH limit.

    Only DAILY, WEEKLY and MONTHLY are limited by BYMONTH; for YEARLY and for
    rules without BYMONTH every step is returned as is. ``None`` when no such
    period starts on or before ``limit`` (by default, the end of year 9999).
    """
    if not plan.by_month or plan.freq is Frequency.YEARLY:
        return step
    while (period := period_at(plan, step)) is not None:
        if limit is not None and period.first > limit:
            return None
        if _months_of(period) & plan.by_month:
            return step
        target = next_allowed_month_start(period.last, plan.by_month)
        if target is None:
            return None
        step = max(step + 1, first_step_ending_at_or_after(plan, target))
    return None


def occurrences_from(
    rule: Rule,
    start: Occurrence,
    *,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Iterator[Occurrence]:
    """Occurrences of a rule without COUNT, starting with the period that contains ``start``.

    Every occurrence on or after ``start`` is produced; a few earlier ones of
    the first period may be produced too, the caller filters them.
    """
    if not can_jump(rule):
        raise ValueError("a rule with COUNT must be iterated from DTSTART")
    plan = plan_for(rule)
    bound = effective_until(rule, until)
    bound_day = bound.date() if isinstance(bound, datetime) else bound
    start_day = start.date() if isinstance(start, datetime) else start
    limits = limits_for(plan)
    step: int | None = first_step_ending_at_or_after(plan, max(start_day, plan.start))
    while step is not None:
        step = next_productive_step(plan, step, bound_day)
        period = period_at(plan, step) if step is not None else None
        if step is None or period is None:
            return
        if bound_day is not None and period.first > bound_day:
            return
        for day in period_occurrences(plan, period, limits):
            if day < plan.start:
                continue
            value = plan.combine(day)
            if bound is not None and value > bound:
                return
            if is_valid is None or is_valid(value):
                yield value
        step += 1


def candidates_from(
    rule: Rule,
    start: Occurrence,
    *,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Iterator[Occurrence]:
    """The cheapest exact source of occurrences for a query beginning at ``start``."""
    if can_jump(rule):
        return occurrences_from(rule, start, is_valid=is_valid, until=until)
    return occurrences(rule, is_valid=is_valid, until=until)
