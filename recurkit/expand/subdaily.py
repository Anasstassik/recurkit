from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from math import gcd

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


DAY_UNITS = {Frequency.HOURLY: 24, Frequency.MINUTELY: 24 * 60, Frequency.SECONDLY: 24 * 3600}


@dataclass(frozen=True)
class TimeCycle:
    length: int
    residues: tuple[int, ...]

    def next_index(self, index: int) -> int | None:
        if not self.residues:
            return None
        base, rest = divmod(index, self.length)
        position = bisect_left(self.residues, rest)
        if position == len(self.residues):
            return (base + 1) * self.length + self.residues[0]
        return base * self.length + self.residues[position]


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
    cycle: TimeCycle | None

    def index_at(self, moment: datetime) -> int:
        return (moment - self.origin) // self.step

    def next_index(self, index: int) -> int | None:
        return index if self.cycle is None else self.cycle.next_index(index)

    def day_matches(self, day: date) -> bool:
        return all(check(day) for check in self.day_limits)

    def values_in(self, start: datetime) -> list[datetime]:
        if self.freq is Frequency.HOURLY:
            return [start.replace(minute=m, second=s) for m, s in self.times]
        if self.freq is Frequency.MINUTELY:
            return [start.replace(second=s) for s in sorted({s for _, s in self.times})]
        return [start]


def _matching_units(
    freq: Frequency, hours: frozenset[int], minutes: frozenset[int], seconds: frozenset[int]
) -> tuple[int, ...] | None:
    limits = [hours]
    if freq is not Frequency.HOURLY:
        limits.append(minutes)
    if freq is Frequency.SECONDLY:
        limits.append(seconds)
    if not any(limits):
        return None
    units = [0]
    for limit, size in zip(limits, (24, 60, 60), strict=False):
        allowed = sorted(limit) if limit else range(size)
        units = [unit * size + value for unit in units for value in allowed]
    return tuple(units)


@lru_cache(maxsize=256)
def time_cycle(day_units: int, offset: int, step: int, matches: tuple[int, ...]) -> TimeCycle:
    common = gcd(step, day_units)
    length = day_units // common
    inverse = pow(step // common, -1, length)
    residues = {
        (match - offset) // common * inverse % length
        for match in matches
        if (match - offset) % common == 0
    }
    return TimeCycle(length, tuple(sorted(residues)))


def _offset(origin: datetime, freq: Frequency) -> int:
    seconds = origin.hour * 3600 + origin.minute * 60 + origin.second
    return seconds * DAY_UNITS[freq] // DAY_UNITS[Frequency.SECONDLY]


def _set_pos_reachable(rule: Rule, times: tuple[tuple[int, int], ...]) -> bool:
    per_period = 1
    if rule.freq is Frequency.HOURLY:
        per_period = len(times)
    elif rule.freq is Frequency.MINUTELY:
        per_period = len({second for _, second in times})
    return not rule.by_set_pos or any(abs(pos) <= per_period for pos in rule.by_set_pos)


def sub_daily_plan(rule: Rule) -> SubDailyPlan:
    start = rule.require_dtstart()
    dtstart = start if isinstance(start, datetime) else datetime.combine(start, time())
    origin = dtstart.replace(microsecond=0)
    if rule.freq is not Frequency.SECONDLY:
        origin = origin.replace(second=0)
    if rule.freq is Frequency.HOURLY:
        origin = origin.replace(minute=0)
    hours, minutes, seconds = (frozenset(p) for p in (rule.by_hour, rule.by_minute, rule.by_second))
    matches = _matching_units(rule.freq, hours, minutes, seconds)
    cycle = None
    times = tuple(sorted({(t.minute, t.second) for t in rule.times_of_day()}))
    if not _set_pos_reachable(rule, times):
        cycle = TimeCycle(1, ())
    elif matches is not None:
        units = DAY_UNITS[rule.freq]
        cycle = time_cycle(units, _offset(origin, rule.freq), rule.interval, matches)
    return SubDailyPlan(
        freq=rule.freq,
        origin=origin,
        step=UNITS[rule.freq] * rule.interval,
        day_limits=_day_limits(rule),
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        times=times,
        by_set_pos=tuple(sorted(set(rule.by_set_pos))),
        cycle=cycle,
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
    index = plan.next_index(max(first_index, 0))
    while index is not None:
        try:
            start = plan.origin + plan.step * index
        except OverflowError:
            return
        if bound is not None and _after(start, bound):
            return
        report_expanded_period()
        if not plan.day_matches(start.date()):
            index = plan.next_index(max(index + 1, _first_index_on_next_day(plan, start)))
            continue
        yield from apply_set_pos(plan.values_in(start), plan.by_set_pos)
        index = plan.next_index(index + 1)


def _first_index_on_next_day(plan: SubDailyPlan, start: datetime) -> int:
    if start.date() == date.max:
        return plan.index_at(datetime.max) + 1
    next_day = datetime.combine(start.date() + timedelta(days=1), time())
    return -((plan.origin - next_day) // plan.step)


def _after(start: datetime, bound: date) -> bool:
    if isinstance(bound, datetime):
        return start > bound
    return start.date() > bound
