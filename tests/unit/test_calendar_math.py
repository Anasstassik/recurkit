from datetime import date

import pytest

from recurkit import calendar_math as cm


@pytest.mark.parametrize(
    ("year", "leap"),
    [(1900, False), (2000, True), (2100, False), (2024, True), (2026, False), (1600, True)],
)
def test_leap_year_boundaries(year: int, leap: bool) -> None:
    assert cm.is_leap_year(year) is leap
    assert cm.days_in_year(year) == (366 if leap else 365)
    assert cm.days_in_month(year, 2) == (29 if leap else 28)


def test_days_in_month_and_valid_dates() -> None:
    assert [cm.days_in_month(2026, m) for m in range(1, 13)] == [
        31,
        28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    assert cm.is_valid_date(2024, 2, 29)
    assert not cm.is_valid_date(2100, 2, 29)
    assert not cm.is_valid_date(2026, 2, 30)
    assert not cm.is_valid_date(2026, 4, 31)
    assert not cm.is_valid_date(10000, 1, 1)
    with pytest.raises(ValueError):
        cm.days_in_month(2026, 13)


@pytest.mark.parametrize(
    "value",
    [
        date(1, 1, 1),
        date(1900, 2, 28),
        date(1900, 3, 1),
        date(2000, 2, 29),
        date(2000, 12, 31),
        date(2024, 12, 31),
        date(2100, 3, 1),
        date(9999, 12, 31),
    ],
)
def test_ordinal_matches_standard_library(value: date) -> None:
    ordinal = cm.date_to_ordinal(value)
    assert ordinal == value.toordinal()
    assert cm.date_from_ordinal(ordinal) == value
    assert cm.weekday_index(value.year, value.month, value.day) == value.weekday()


def test_day_of_year_roundtrip() -> None:
    assert cm.day_of_year(2026, 1, 1) == 1
    assert cm.day_of_year(2024, 12, 31) == 366
    assert cm.day_of_year(2026, 3, 1) == 60
    assert cm.day_of_year(2024, 3, 1) == 61
    assert cm.date_from_day_of_year(2024, 60) == date(2024, 2, 29)
    assert cm.date_from_day_of_year(2026, -1) == date(2026, 12, 31)
    assert cm.date_from_day_of_year(2026, 366) is None
    assert cm.add_days(date(2024, 2, 28), 2) == date(2024, 3, 1)
    assert cm.days_between(date(2026, 1, 1), date(2025, 12, 1)) == -31


def test_rrule_16_invalid_month_days_are_skipped_not_moved() -> None:
    assert cm.resolve_month_day(2026, 4, 31) is None
    assert cm.resolve_month_day(2026, 2, 29) is None
    assert cm.resolve_month_day(2024, 2, 29) == 29
    assert cm.resolve_month_day(2026, 2, -1) == 28
    assert cm.resolve_month_day(2026, 1, -31) == 1
    assert cm.resolve_month_day(2026, 2, -30) is None


def test_weekday_codes_and_lookup() -> None:
    assert cm.Weekday.from_code("tu") is cm.Weekday.TU
    assert cm.Weekday.SU.code == "SU"
    assert cm.Weekday.of(date(2026, 11, 16)) is cm.Weekday.MO
    assert [w.code for w in cm.Weekday] == ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    with pytest.raises(ValueError, match="unknown weekday"):
        cm.Weekday.from_code("XX")


def test_nth_weekday_of_month_positive_and_negative() -> None:
    assert cm.nth_weekday_of_month(2026, 1, cm.Weekday.TU, 2) == date(2026, 1, 13)
    assert cm.nth_weekday_of_month(2026, 6, cm.Weekday.TU, 2) == date(2026, 6, 9)
    assert cm.nth_weekday_of_month(2026, 1, cm.Weekday.FR, -1) == date(2026, 1, 30)
    assert cm.nth_weekday_of_month(2026, 2, cm.Weekday.FR, -1) == date(2026, 2, 27)
    assert cm.nth_weekday_of_month(2026, 1, cm.Weekday.TH, 1) == date(2026, 1, 1)
    assert cm.nth_weekday_of_month(2026, 1, cm.Weekday.SA, -5) == date(2026, 1, 3)


def test_missing_fifth_weekday_returns_none() -> None:
    assert cm.nth_weekday_of_month(2026, 2, cm.Weekday.MO, 5) is None
    assert cm.nth_weekday_of_month(2026, 2, cm.Weekday.MO, -5) is None
    assert cm.nth_weekday_of_month(2026, 3, cm.Weekday.MO, 5) == date(2026, 3, 30)
    with pytest.raises(ValueError, match="zero"):
        cm.nth_weekday_of_month(2026, 3, cm.Weekday.MO, 0)


def test_nth_weekday_of_year_and_ordinals() -> None:
    assert cm.nth_weekday_of_year(2026, cm.Weekday.MO, 20) == date(2026, 5, 18)
    assert cm.nth_weekday_of_year(2026, cm.Weekday.SU, -1) == date(2026, 12, 27)
    assert cm.nth_weekday_of_year(2026, cm.Weekday.TH, 53) == date(2026, 12, 31)
    assert cm.nth_weekday_of_year(2026, cm.Weekday.FR, 53) is None
    assert len(cm.weekdays_of_year(2026, cm.Weekday.TH)) == 53
    assert cm.weekdays_of_month(2026, 1, cm.Weekday.FR)[-1] == date(2026, 1, 30)
    assert cm.weekday_ordinals_in_month(date(2026, 1, 30)) == (5, -1)
    assert cm.weekday_ordinals_in_year(date(2026, 1, 1)) == (1, -53)


@pytest.mark.parametrize(
    ("wkst", "expected"),
    [
        (cm.Weekday.MO, date(2026, 11, 16)),
        (cm.Weekday.SU, date(2026, 11, 15)),
        (cm.Weekday.WE, date(2026, 11, 18)),
        (cm.Weekday.TH, date(2026, 11, 12)),
    ],
)
def test_rrule_21_week_start_follows_wkst(wkst: cm.Weekday, expected: date) -> None:
    assert cm.week_start(date(2026, 11, 18), wkst) == expected
    assert cm.weekday_offset(cm.Weekday.MO, cm.Weekday.SU) == 1


def test_months_between_and_add_months() -> None:
    assert cm.months_between(date(2026, 1, 31), date(2026, 2, 1)) == 1
    assert cm.months_between(date(2026, 3, 15), date(2025, 12, 1)) == -3
    assert cm.add_months(2026, 11, 3) == (2027, 2)
    assert cm.add_months(2026, 1, -1) == (2025, 12)
    assert cm.add_months(2026, 1, -13) == (2024, 12)
    with pytest.raises(ValueError):
        cm.add_months(9999, 12, 1)


def test_weeks_between_depends_on_wkst() -> None:
    sunday, monday = date(2026, 11, 15), date(2026, 11, 16)
    assert cm.weeks_between(sunday, monday, cm.Weekday.MO) == 1
    assert cm.weeks_between(sunday, monday, cm.Weekday.SU) == 0
    assert cm.weeks_between(date(2026, 12, 31), date(2026, 1, 1)) == -52
    assert cm.add_weeks(date(2026, 12, 28), 1) == date(2027, 1, 4)
    assert cm.next_multiple_at_or_after(7, 3) == 9
    assert cm.next_multiple_at_or_after(-7, 3) == -6
