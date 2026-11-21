from datetime import date, datetime

from recurkit import Rule
from recurkit.expand import plan_for
from recurkit.expand.expanders import expand_monthly, expand_period, expand_yearly
from recurkit.expand.filters import limits_for
from recurkit.expand.periods import Period, period_at


def _monthly(text: str, dtstart: datetime, year: int, month: int) -> list[date]:
    plan = plan_for(Rule.parse(text, dtstart=dtstart))
    first = date(year, month, 1)
    period = Period(0, first, date(year, month, 28))
    return expand_monthly(plan, period, limits_for(plan))


def _yearly(text: str, dtstart: datetime, year: int) -> list[date]:
    plan = plan_for(Rule.parse(text, dtstart=dtstart))
    return expand_yearly(plan, Period(0, date(year, 1, 1), date(year, 12, 31)), limits_for(plan))


def test_rrule_16_monthly_31st_is_skipped_in_short_months() -> None:
    start = datetime(2026, 1, 31, 9)
    assert _monthly("FREQ=MONTHLY", start, 2026, 1) == [date(2026, 1, 31)]
    assert _monthly("FREQ=MONTHLY", start, 2026, 2) == []
    assert _monthly("FREQ=MONTHLY", start, 2026, 4) == []
    assert _monthly("FREQ=MONTHLY;BYMONTHDAY=-1,1,1", start, 2026, 2) == [
        date(2026, 2, 1),
        date(2026, 2, 28),
    ]


def test_monthly_nth_weekdays_2tu_and_last_friday() -> None:
    start = datetime(2026, 1, 6, 10)
    assert _monthly("FREQ=MONTHLY;BYDAY=2TU", start, 2026, 6) == [date(2026, 6, 9)]
    assert _monthly("FREQ=MONTHLY;BYDAY=-1FR,2TU", start, 2026, 1) == [
        date(2026, 1, 13),
        date(2026, 1, 30),
    ]
    assert _monthly("FREQ=MONTHLY;BYDAY=5MO", start, 2026, 2) == []
    assert len(_monthly("FREQ=MONTHLY;BYDAY=SA,SU", start, 2026, 1)) == 9
    assert _monthly("FREQ=MONTHLY;BYMONTH=3;BYDAY=2TU", start, 2026, 1) == []
    assert _monthly("FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13", start, 2026, 2) == [date(2026, 2, 13)]
    assert _monthly("FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13", start, 2026, 1) == []


def test_rrule_16_february_29_only_in_leap_years() -> None:
    start = datetime(2024, 2, 29, 12)
    assert _yearly("FREQ=YEARLY", start, 2024) == [date(2024, 2, 29)]
    assert _yearly("FREQ=YEARLY", start, 2025) == []
    assert _yearly("FREQ=YEARLY", start, 2100) == []
    assert _yearly("FREQ=YEARLY", start, 2000) == [date(2000, 2, 29)]


def test_rrule_20_yearly_by_day_with_and_without_by_month() -> None:
    start = datetime(2026, 1, 1)
    assert _yearly("FREQ=YEARLY;BYMONTH=3,10;BYDAY=-1SU", start, 2026) == [
        date(2026, 3, 29),
        date(2026, 10, 25),
    ]
    assert _yearly("FREQ=YEARLY;BYDAY=20MO", start, 1997) == [date(1997, 5, 19)]
    assert len(_yearly("FREQ=YEARLY;BYDAY=TH", start, 2026)) == 53
    assert _yearly("FREQ=YEARLY;BYDAY=53FR", start, 2026) == []


def test_yearly_by_month_day_expands_every_listed_month() -> None:
    start = datetime(2026, 1, 1)
    assert _yearly("FREQ=YEARLY;BYMONTH=2,4;BYMONTHDAY=30,-1", start, 2026) == [
        date(2026, 2, 28),
        date(2026, 4, 30),
    ]
    assert len(_yearly("FREQ=YEARLY;BYMONTHDAY=31", start, 2026)) == 7
    plan = plan_for(Rule.parse("FREQ=YEARLY;INTERVAL=4", dtstart=start))
    period = period_at(plan, 1)
    assert period is not None
    assert expand_yearly(plan, period, limits_for(plan)) == [date(2030, 1, 1)]


def _weeks(text: str, dtstart: datetime, n: int) -> list[date]:
    plan = plan_for(Rule.parse(text, dtstart=dtstart))
    days: list[date] = []
    for step in range(n):
        period = period_at(plan, step)
        assert period is not None
        days.extend(expand_period(plan, period))
    return days


def test_rrule_21_wkst_changes_biweekly_result() -> None:
    start = datetime(1997, 8, 5, 9)
    monday_weeks = _weeks("FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO", start, 2)
    assert monday_weeks == [
        date(1997, 8, 5),
        date(1997, 8, 10),
        date(1997, 8, 19),
        date(1997, 8, 24),
    ]
    sunday_weeks = _weeks("FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU", start, 3)
    assert sunday_weeks[0] == date(1997, 8, 3)
    assert sunday_weeks[1:5] == [
        date(1997, 8, 5),
        date(1997, 8, 17),
        date(1997, 8, 19),
        date(1997, 8, 31),
    ]


def test_weekly_by_month_limits_days_of_a_straddling_week() -> None:
    days = _weeks("FREQ=WEEKLY;BYDAY=MO,FR;BYMONTH=2", datetime(2026, 1, 26), 2)
    assert days == [date(2026, 2, 2), date(2026, 2, 6)]


def test_rrule_19_daily_by_day_is_a_limit() -> None:
    days = _weeks("FREQ=DAILY;BYDAY=MO,WE,FR", datetime(2026, 11, 16), 7)
    assert days == [date(2026, 11, 16), date(2026, 11, 18), date(2026, 11, 20)]
    leap = _weeks("FREQ=DAILY;BYMONTH=2;BYMONTHDAY=-1", datetime(2024, 2, 27), 3)
    assert leap == [date(2024, 2, 29)]
