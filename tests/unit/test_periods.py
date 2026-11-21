from collections.abc import Iterator
from datetime import date, datetime
from itertools import islice

from recurkit import Rule, Weekday
from recurkit.expand import plan_for
from recurkit.expand.periods import (
    Period,
    first_step_ending_at_or_after,
    iter_periods,
    period_at,
    period_start,
    shift_period_start,
    step_containing,
)
from recurkit.rule import Frequency


def _take(periods: Iterator[Period], n: int) -> list[Period]:
    return list(islice(periods, n))


def test_periods_for_every_frequency_with_interval() -> None:
    start = datetime(2026, 1, 31, 9)
    yearly = plan_for(Rule.parse("FREQ=YEARLY;INTERVAL=2", dtstart=start))
    assert [p.first for p in _take(iter_periods(yearly), 3)] == [
        date(2026, 1, 1),
        date(2028, 1, 1),
        date(2030, 1, 1),
    ]
    monthly = plan_for(Rule.parse("FREQ=MONTHLY;INTERVAL=5", dtstart=start))
    assert [(p.first, p.last) for p in _take(iter_periods(monthly), 3)] == [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 11, 1), date(2026, 11, 30)),
    ]
    weekly = plan_for(Rule.parse("FREQ=WEEKLY;INTERVAL=2", dtstart=start))
    assert [p.first for p in _take(iter_periods(weekly), 2)] == [
        date(2026, 1, 26),
        date(2026, 2, 9),
    ]
    daily = plan_for(Rule.parse("FREQ=DAILY;INTERVAL=3", dtstart=start))
    assert [p.first for p in _take(iter_periods(daily), 2)] == [date(2026, 1, 31), date(2026, 2, 3)]


def test_period_boundaries_across_months_and_leap_years() -> None:
    plan = plan_for(Rule.parse("FREQ=MONTHLY", dtstart=datetime(2024, 1, 15)))
    feb = period_at(plan, 1)
    assert feb == Period(1, date(2024, 2, 1), date(2024, 2, 29))
    assert feb is not None and feb.length == 29 and date(2024, 2, 29) in feb
    assert list(Period(0, date(2026, 12, 30), date(2027, 1, 1)).days())[-1] == date(2027, 1, 1)
    assert shift_period_start(Frequency.MONTHLY, date(2026, 11, 1), 3) == date(2027, 2, 1)
    assert shift_period_start(Frequency.YEARLY, date(9999, 1, 1), 1) is None
    assert period_at(plan_for(Rule.parse("FREQ=YEARLY", dtstart=datetime(9999, 1, 1))), 1) is None


def test_rrule_21_weekly_periods_start_on_wkst() -> None:
    tuesday = date(2026, 11, 17)
    assert period_start(Frequency.WEEKLY, tuesday, Weekday.MO) == date(2026, 11, 16)
    assert period_start(Frequency.WEEKLY, tuesday, Weekday.SU) == date(2026, 11, 15)
    assert period_start(Frequency.WEEKLY, tuesday, Weekday.WE) == date(2026, 11, 11)
    plan = plan_for(Rule.parse("FREQ=WEEKLY;INTERVAL=2;WKST=SU", dtstart=datetime(2026, 11, 17)))
    second = period_at(plan, 1)
    assert second is not None
    assert (second.first, second.last) == (date(2026, 11, 29), date(2026, 12, 5))


def test_jump_to_step_of_a_far_date() -> None:
    plan = plan_for(Rule.parse("FREQ=WEEKLY;INTERVAL=2", dtstart=datetime(2026, 1, 5)))
    assert step_containing(plan, date(2026, 1, 11)) == 0
    assert step_containing(plan, date(2026, 1, 12)) == 0
    assert step_containing(plan, date(2026, 1, 19)) == 1
    assert step_containing(plan, date(2025, 12, 31)) == -1
    assert first_step_ending_at_or_after(plan, date(2026, 1, 12)) == 1
    assert first_step_ending_at_or_after(plan, date(2025, 1, 1)) == 0
    target = date(2036, 1, 1)
    far = first_step_ending_at_or_after(plan, target)
    period, previous = period_at(plan, far), period_at(plan, far - 1)
    assert period is not None and previous is not None
    assert previous.last < target <= period.last
