from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from recurkit import calendar_math as cm

dates = st.dates(min_value=date(1, 1, 8), max_value=date(9999, 12, 24))
weekdays = st.sampled_from(list(cm.Weekday))


@given(start=dates, end=dates, wkst=weekdays)
def test_week_arithmetic_is_consistent(start: date, end: date, wkst: cm.Weekday) -> None:
    weeks = cm.weeks_between(start, end, wkst)
    shifted = cm.week_start(start, wkst) + timedelta(weeks=weeks)
    assert shifted == cm.week_start(end, wkst)
    assert cm.Weekday.of(cm.week_start(end, wkst)) is wkst
    assert 0 <= (end - cm.week_start(end, wkst)).days < 7


@given(start=dates, months=st.integers(min_value=-1200, max_value=1200))
def test_add_months_inverts_months_between(start: date, months: int) -> None:
    index = cm.month_index(start.year, start.month) + months
    if not 1 <= index // 12 <= 9999:
        return
    year, month = cm.add_months(start.year, start.month, months)
    assert cm.months_between(start, date(year, month, 1)) == months
    assert cm.month_from_index(cm.month_index(year, month)) == (year, month)
