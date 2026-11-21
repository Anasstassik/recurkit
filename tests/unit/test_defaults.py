from datetime import date, datetime, time

from recurkit import Rule, Weekday, WeekdayNum
from recurkit.expand import plan_for

DTSTART = datetime(2026, 3, 15, 10, 30)


def test_rrule_18_monthly_and_yearly_take_day_and_month_from_dtstart() -> None:
    monthly = plan_for(Rule.parse("FREQ=MONTHLY", dtstart=DTSTART))
    assert monthly.by_month_day == (15,)
    assert monthly.by_month == frozenset()
    yearly = plan_for(Rule.parse("FREQ=YEARLY", dtstart=DTSTART))
    assert yearly.by_month == frozenset({3})
    assert yearly.by_month_day == (15,)
    by_month = plan_for(Rule.parse("FREQ=YEARLY;BYMONTH=1,7", dtstart=DTSTART))
    assert by_month.by_month == frozenset({1, 7})
    assert by_month.by_month_day == (15,)


def test_rrule_18_weekly_takes_weekday_from_dtstart() -> None:
    weekly = plan_for(Rule.parse("FREQ=WEEKLY;INTERVAL=2", dtstart=DTSTART))
    assert weekly.weekdays == frozenset({Weekday.SU})
    explicit = plan_for(Rule.parse("FREQ=WEEKLY;BYDAY=MO,WE", dtstart=DTSTART))
    assert explicit.weekdays == frozenset({Weekday.MO, Weekday.WE})
    daily = plan_for(Rule.parse("FREQ=DAILY", dtstart=DTSTART))
    assert not daily.weekdays and not daily.by_month_day and not daily.by_month


def test_explicit_parts_are_not_overridden_and_are_normalized() -> None:
    plan = plan_for(
        Rule.parse("FREQ=YEARLY;BYDAY=-1FR,MO,-1FR,2TU;BYSETPOS=3,1,3", dtstart=DTSTART)
    )
    assert plan.by_month == frozenset()
    assert plan.by_month_day == ()
    assert plan.weekdays == frozenset({Weekday.MO})
    assert plan.nth_weekdays == (WeekdayNum(Weekday.TU, 2), WeekdayNum(Weekday.FR, -1))
    assert plan.by_set_pos == (1, 3)
    assert plan.start_time == time(10, 30)
    assert plan.combine(date(2026, 4, 1)) == datetime(2026, 4, 1, 10, 30)
    assert plan_for(Rule.parse("FREQ=DAILY", dtstart=date(2026, 1, 1))).start_time is None
