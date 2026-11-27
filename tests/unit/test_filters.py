from datetime import date, datetime

from recurkit import Rule, Weekday
from recurkit.expand import plan_for
from recurkit.expand.defaults import NthWeekday
from recurkit.expand.filters import (
    OrdinalScope,
    apply_limits,
    limits_for,
    month_day_matches,
    month_matches,
    ordinal_scope,
    weekday_matches,
)


def test_month_and_negative_month_day_limits() -> None:
    assert month_matches(date(2026, 1, 5), frozenset({1, 3}))
    assert not month_matches(date(2026, 2, 5), frozenset({1, 3}))
    assert month_matches(date(2026, 2, 5), frozenset())
    assert month_day_matches(date(2026, 2, 28), (-1,))
    assert month_day_matches(date(2024, 2, 28), (-2,))
    assert not month_day_matches(date(2024, 2, 28), (-1,))
    assert month_day_matches(date(2026, 1, 1), (-31,))
    assert month_day_matches(date(2026, 1, 15), (15, -1))


def test_rrule_20_numeric_by_day_counts_in_month_or_year() -> None:
    last_friday = (NthWeekday(Weekday.FR, -1),)
    assert weekday_matches(date(2026, 1, 30), frozenset(), last_friday, OrdinalScope.MONTH)
    assert not weekday_matches(date(2026, 1, 23), frozenset(), last_friday, OrdinalScope.MONTH)
    assert not weekday_matches(date(2026, 1, 30), frozenset(), last_friday, OrdinalScope.YEAR)
    assert weekday_matches(date(2026, 12, 25), frozenset(), last_friday, OrdinalScope.YEAR)
    assert weekday_matches(date(2026, 1, 13), frozenset({Weekday.TU}), ())
    assert not weekday_matches(date(2026, 1, 14), frozenset({Weekday.TU}), last_friday)
    yearly = plan_for(Rule.parse("FREQ=YEARLY;BYDAY=20MO", dtstart=datetime(2026, 1, 1)))
    assert ordinal_scope(yearly) is OrdinalScope.YEAR
    monthly_in_year = plan_for(
        Rule.parse("FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", dtstart=datetime(2026, 1, 1))
    )
    assert ordinal_scope(monthly_in_year) is OrdinalScope.MONTH


def test_rrule_19_daily_limits_by_month_month_day_and_day() -> None:
    plan = plan_for(
        Rule.parse(
            "FREQ=DAILY;BYMONTH=1;BYMONTHDAY=1,2,3,13;BYDAY=TU,FR", dtstart=datetime(2026, 1, 1)
        )
    )
    assert len(limits_for(plan)) == 3
    january = [date(2026, 1, d) for d in range(1, 32)]
    assert apply_limits(january, limits_for(plan)) == [date(2026, 1, 2), date(2026, 1, 13)]
    assert apply_limits([date(2026, 2, 13)], limits_for(plan)) == []


def test_rrule_19_by_day_limits_monthly_only_with_by_month_day() -> None:
    friday_13 = plan_for(
        Rule.parse("FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13", dtstart=datetime(2026, 2, 13))
    )
    assert len(limits_for(friday_13)) == 1
    expand_only = plan_for(Rule.parse("FREQ=MONTHLY;BYDAY=FR", dtstart=datetime(2026, 2, 13)))
    assert limits_for(expand_only) == ()
    yearly = plan_for(Rule.parse("FREQ=YEARLY;BYMONTH=1,2", dtstart=datetime(2026, 2, 13)))
    assert limits_for(yearly) == ()
    weekly = plan_for(Rule.parse("FREQ=WEEKLY;BYMONTH=1", dtstart=datetime(2026, 1, 5)))
    assert apply_limits([date(2026, 1, 26), date(2026, 2, 2)], limits_for(weekly)) == [
        date(2026, 1, 26)
    ]
