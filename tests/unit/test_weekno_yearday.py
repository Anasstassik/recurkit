from datetime import date, datetime
from itertools import islice

import pytest

from recurkit import RuleValidationError
from recurkit import calendar_math as cm
from recurkit.calendar_math import Weekday
from recurkit.expand import occurrences
from recurkit.rule import Rule, parse_rrule, validate


def _requirement(text: str) -> str:
    with pytest.raises(RuleValidationError) as info:
        validate(parse_rrule(text))
    return info.value.requirement_id


def test_rrule_23_by_year_day_not_with_daily_weekly_monthly() -> None:
    for freq in ("DAILY", "WEEKLY", "MONTHLY"):
        assert _requirement(f"FREQ={freq};BYYEARDAY=100") == "RRULE-23"
    validate(parse_rrule("FREQ=YEARLY;BYYEARDAY=1,-1"))
    assert _requirement("FREQ=YEARLY;BYYEARDAY=367") == "RRULE-06"


def test_rrule_24_and_25_by_week_no_only_yearly_without_numeric_by_day() -> None:
    assert _requirement("FREQ=MONTHLY;BYWEEKNO=20") == "RRULE-24"
    assert _requirement("FREQ=YEARLY;BYWEEKNO=20;BYDAY=1MO") == "RRULE-25"
    assert _requirement("FREQ=YEARLY;BYWEEKNO=54") == "RRULE-06"
    rule = parse_rrule("FREQ=YEARLY;BYWEEKNO=20,-1;BYYEARDAY=1;BYDAY=MO")
    assert rule.to_text() == "FREQ=YEARLY;BYWEEKNO=20,-1;BYYEARDAY=1;BYDAY=MO"


def test_rrule_26_week_one_has_four_days_of_the_year() -> None:
    assert cm.first_week_start(2026, Weekday.MO) == date(2025, 12, 29)  # ISO 2026-W01
    assert cm.first_week_start(2027, Weekday.MO) == date(2027, 1, 4)
    assert cm.first_week_start(2026, Weekday.SU) == date(2026, 1, 4)
    assert cm.week_number(date(2027, 1, 1)) == (2026, 53, 53)
    assert cm.week_number(date(2025, 12, 30)) == (2026, 1, 53)
    assert cm.WeekNumbering.for_year(2026).weeks == 53
    assert cm.week_number(date(2026, 11, 16), Weekday.SU) == (2026, 46, 52)


def test_by_week_no_and_by_year_day_expand_yearly() -> None:
    start = datetime(2026, 1, 1, 9)
    last_week = list(
        islice(occurrences(Rule.parse("FREQ=YEARLY;BYWEEKNO=-1;BYDAY=FR", dtstart=start)), 2)
    )
    # The last week of 2026 is W53 (28.12.2026-03.01.2027): its Friday is 1 January 2027.
    assert last_week == [datetime(2027, 1, 1, 9), datetime(2027, 12, 31, 9)]
    whole_week = list(occurrences(Rule.parse("FREQ=YEARLY;BYWEEKNO=1;COUNT=7", dtstart=start)))
    assert [d.day for d in whole_week] == [1, 2, 3, 4, 4, 5, 6]  # type: ignore[union-attr]
    yearly_last_day = list(
        islice(occurrences(Rule.parse("FREQ=YEARLY;BYYEARDAY=-1,60", dtstart=start)), 4)
    )
    assert yearly_last_day == [
        datetime(2026, 3, 1, 9),
        datetime(2026, 12, 31, 9),
        datetime(2027, 3, 1, 9),
        datetime(2027, 12, 31, 9),
    ]
