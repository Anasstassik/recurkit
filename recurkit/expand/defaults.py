"""Derive the rule parts that the generator needs from DTSTART (RRULE-18).

RFC 5545: information not contained in the rule (day, month, weekday) is
taken from DTSTART. ``FREQ=MONTHLY`` starting on the 15th means "every 15th",
``FREQ=YEARLY;BYMONTH=3`` means "every year on DTSTART's day of March".
The result is an :class:`ExpansionPlan`: the rule with all defaults filled in,
normalized into the shapes the expanders work with.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from recurkit.calendar_math import Weekday
from recurkit.rule.model import Frequency, Rule, WeekdayNum


@dataclass(frozen=True)
class ExpansionPlan:
    """A rule with implicit parts made explicit.

    ``weekdays`` holds plain BYDAY values (``MO``), ``nth_weekdays`` the
    numeric ones (``2TU``, ``-1FR``). ``start_time`` is ``None`` for an all-day
    (DATE) series.
    """

    freq: Frequency
    interval: int
    start: date
    start_time: time | None
    by_month: frozenset[int]
    by_month_day: tuple[int, ...]
    weekdays: frozenset[Weekday]
    nth_weekdays: tuple[WeekdayNum, ...]
    by_set_pos: tuple[int, ...]
    wkst: Weekday

    @property
    def has_by_day(self) -> bool:
        return bool(self.weekdays or self.nth_weekdays)

    def combine(self, day: date) -> date | datetime:
        """Attach DTSTART's time of day to a generated date."""
        if self.start_time is None:
            return day
        return datetime.combine(day, self.start_time)


def split_by_day(
    by_day: tuple[WeekdayNum, ...],
) -> tuple[frozenset[Weekday], tuple[WeekdayNum, ...]]:
    """Separate plain weekdays from numeric ones; numeric values are de-duplicated."""
    plain = frozenset(item.weekday for item in by_day if item.n is None)
    numeric = tuple(sorted({item for item in by_day if item.n is not None}, key=_by_day_key))
    return plain, numeric


def _by_day_key(item: WeekdayNum) -> tuple[int, int]:
    return item.weekday.value, item.n or 0


def plan_for(rule: Rule) -> ExpansionPlan:
    """Build the expansion plan of ``rule`` (which must have a DTSTART)."""
    dtstart = rule.require_dtstart()
    if isinstance(dtstart, datetime):
        start, start_time = dtstart.date(), dtstart.timetz()
    else:
        start, start_time = dtstart, None

    by_month = set(rule.by_month)
    by_month_day = tuple(rule.by_month_day)
    weekdays, nth_weekdays = split_by_day(rule.by_day)
    has_by_day = bool(rule.by_day)

    if rule.freq is Frequency.WEEKLY and not has_by_day:
        weekdays = frozenset({Weekday.of(start)})
    elif rule.freq is Frequency.MONTHLY and not has_by_day and not by_month_day:
        by_month_day = (start.day,)
    elif rule.freq is Frequency.YEARLY and not has_by_day and not by_month_day:
        if not by_month:
            by_month = {start.month}
        by_month_day = (start.day,)

    return ExpansionPlan(
        freq=rule.freq,
        interval=rule.interval,
        start=start,
        start_time=start_time,
        by_month=frozenset(by_month),
        by_month_day=tuple(sorted(set(by_month_day))),
        weekdays=weekdays,
        nth_weekdays=nth_weekdays,
        by_set_pos=tuple(sorted(set(rule.by_set_pos))),
        wkst=rule.wkst,
    )
