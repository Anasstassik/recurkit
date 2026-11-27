from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import NamedTuple

from recurkit.calendar_math import Weekday
from recurkit.rule.model import Frequency, Rule, WeekdayNum


class NthWeekday(NamedTuple):
    weekday: Weekday
    n: int


@dataclass(frozen=True)
class ExpansionPlan:
    freq: Frequency
    interval: int
    start: date
    first: date | datetime
    times: tuple[time, ...]
    by_month: frozenset[int]
    by_week_no: tuple[int, ...]
    by_year_day: tuple[int, ...]
    by_month_day: tuple[int, ...]
    weekdays: frozenset[Weekday]
    nth_weekdays: tuple[NthWeekday, ...]
    by_set_pos: tuple[int, ...]
    wkst: Weekday

    @property
    def has_by_day(self) -> bool:
        return bool(self.weekdays or self.nth_weekdays)

    def values_on(self, day: date) -> list[date | datetime]:
        if not self.times:
            return [day]
        return [datetime.combine(day, moment) for moment in self.times]


def split_by_day(
    by_day: tuple[WeekdayNum, ...],
) -> tuple[frozenset[Weekday], tuple[NthWeekday, ...]]:
    plain = frozenset(item.weekday for item in by_day if item.n is None)
    numbered = {NthWeekday(item.weekday, item.n) for item in by_day if item.n is not None}
    return plain, tuple(sorted(numbered, key=lambda item: (item.weekday.value, item.n)))


def plan_for(rule: Rule) -> ExpansionPlan:
    dtstart = rule.require_dtstart()
    start = dtstart.date() if isinstance(dtstart, datetime) else dtstart

    by_month = set(rule.by_month)
    by_month_day = tuple(rule.by_month_day)
    weekdays, nth_weekdays = split_by_day(rule.by_day)
    has_by_day = bool(rule.by_day)

    if rule.freq is Frequency.WEEKLY and not has_by_day:
        weekdays = frozenset({Weekday.of(start)})
    elif rule.freq is Frequency.MONTHLY and not has_by_day and not by_month_day:
        by_month_day = (start.day,)
    elif rule.freq is Frequency.YEARLY and not (
        has_by_day or by_month_day or rule.by_week_no or rule.by_year_day
    ):
        if not by_month:
            by_month = {start.month}
        by_month_day = (start.day,)

    return ExpansionPlan(
        freq=rule.freq,
        interval=rule.interval,
        start=start,
        first=dtstart,
        times=rule.times_of_day(),
        by_month=frozenset(by_month),
        by_week_no=tuple(sorted(set(rule.by_week_no))),
        by_year_day=tuple(sorted(set(rule.by_year_day))),
        by_month_day=tuple(sorted(set(by_month_day))),
        weekdays=weekdays,
        nth_weekdays=nth_weekdays,
        by_set_pos=tuple(sorted(set(rule.by_set_pos))),
        wkst=rule.wkst,
    )
