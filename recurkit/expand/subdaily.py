from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from recurkit.expand.filters import (
    DayFilter,
    OrdinalScope,
    month_day_matches,
    month_matches,
    weekday_matches,
    year_day_matches,
)
from recurkit.expand.setpos import apply_set_pos
from recurkit.expand.work import report_expanded_period
from recurkit.rule.model import Frequency, Rule

UNITS = {
    Frequency.HOURLY: timedelta(hours=1),
    Frequency.MINUTELY: timedelta(minutes=1),
    Frequency.SECONDLY: timedelta(seconds=1),
}


def is_sub_daily(freq: Frequency) -> bool:
    return freq in UNITS


@dataclass(frozen=True)
class SubDailyPlan:
    freq: Frequency
    origin: datetime
    step: timedelta
    day_limits: tuple[DayFilter, ...]
    hours: frozenset[int]
    minutes: frozenset[int]
    seconds: frozenset[int]
    times: tuple[tuple[int, int], ...]
    by_set_pos: tuple[int, ...]

    def index_at(self, moment: datetime) -> int:
        return (moment - self.origin) // self.step

    def skip_to(self, start: datetime) -> datetime | None:
        if not all(check(start.date()) for check in self.day_limits):
            return datetime.combine(start.date() + timedelta(days=1), time(), start.tzinfo)
        if self.hours and start.hour not in self.hours:
            return start.replace(minute=0, second=0) + timedelta(hours=1)
        if self.freq is Frequency.SECONDLY and self.minutes and start.minute not in self.minutes:
            return start.replace(second=0) + timedelta(minutes=1)
        return None

    def values_in(self, start: datetime) -> list[datetime]:
        if self.freq is Frequency.HOURLY:
            return [start.replace(minute=m, second=s) for m, s in self.times]
        if self.minutes and start.minute not in self.minutes:
            return []
        if self.freq is Frequency.MINUTELY:
            return [start.replace(second=s) for s in sorted({s for _, s in self.times})]
        return [start] if not self.seconds or start.second in self.seconds else []


def sub_daily_plan(rule: Rule) -> SubDailyPlan:
    start = rule.require_dtstart()
    dtstart = start if isinstance(start, datetime) else datetime.combine(start, time())
    origin = dtstart.replace(microsecond=0)
    if rule.freq is not Frequency.SECONDLY:
        origin = origin.replace(second=0)
    if rule.freq is Frequency.HOURLY:
        origin = origin.replace(minute=0)
    return SubDailyPlan(
        freq=rule.freq,
        origin=origin,
        step=UNITS[rule.freq] * rule.interval,
        day_limits=_day_limits(rule),
        hours=frozenset(rule.by_hour),
        minutes=frozenset(rule.by_minute),
        seconds=frozenset(rule.by_second),
        times=tuple(sorted({(t.minute, t.second) for t in rule.times_of_day()})),
        by_set_pos=tuple(sorted(set(rule.by_set_pos))),
    )


def _day_limits(rule: Rule) -> tuple[DayFilter, ...]:
    weekdays = frozenset(item.weekday for item in rule.by_day)
    checks: list[DayFilter] = []
    if rule.by_month:
        checks.append(lambda day: month_matches(day, frozenset(rule.by_month)))
    if rule.by_year_day:
        checks.append(lambda day: year_day_matches(day, rule.by_year_day))
    if rule.by_month_day:
        checks.append(lambda day: month_day_matches(day, rule.by_month_day))
    if weekdays:
        checks.append(lambda day: weekday_matches(day, weekdays, (), OrdinalScope.MONTH))
    return tuple(checks)


def sub_daily_values(
    plan: SubDailyPlan, first_index: int, bound: date | None
) -> Iterator[datetime]:
    index = max(first_index, 0)
    while True:
        try:
            start = plan.origin + plan.step * index
            skip = plan.skip_to(start)
        except OverflowError:
            return
        if bound is not None and _after(start, bound):
            return
        report_expanded_period()
        if skip is not None:
            index = max(index + 1, -((plan.origin - skip) // plan.step))
            continue
        yield from apply_set_pos(plan.values_in(start), plan.by_set_pos)
        index += 1


def _after(start: datetime, bound: date) -> bool:
    if isinstance(bound, datetime):
        return start > bound
    return start.date() > bound
