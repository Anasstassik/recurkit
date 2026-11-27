from datetime import UTC, date, datetime, time
from itertools import islice

import pytest

from recurkit import Rule, RuleValidationError, describe
from recurkit.expand import occurrences

START = datetime(2026, 1, 5, 10)


@pytest.mark.parametrize("part", ["BYHOUR=24", "BYHOUR=-1", "BYMINUTE=60", "BYSECOND=60"])
def test_rrule_27_time_parts_are_in_range(part: str) -> None:
    with pytest.raises(RuleValidationError, match="RRULE-27"):
        Rule.parse(f"FREQ=DAILY;{part}", dtstart=START)


def test_rrule_28_time_parts_need_a_date_time_dtstart() -> None:
    with pytest.raises(RuleValidationError, match="RRULE-28"):
        Rule.parse("FREQ=DAILY;BYMINUTE=30", dtstart=date(2026, 1, 5))


def test_rrule_29_every_time_of_day_is_a_value_after_dtstart() -> None:
    rule = Rule.parse("FREQ=DAILY;BYHOUR=17,9;BYMINUTE=30,0;COUNT=6", dtstart=START)
    assert [f"{v:%d %H:%M}" for v in occurrences(rule)] == [
        "05 17:00",
        "05 17:30",
        "06 09:00",
        "06 09:30",
        "06 17:00",
        "06 17:30",
    ]


def test_rrule_29_missing_time_parts_come_from_dtstart() -> None:
    rule = Rule.parse(
        "FREQ=WEEKLY;BYMINUTE=0,45", dtstart=datetime(2026, 1, 5, 8, 15, 20, tzinfo=UTC)
    )
    values = list(islice(occurrences(rule), 3))
    assert values == [
        datetime(2026, 1, 5, 8, 45, 20, tzinfo=UTC),
        datetime(2026, 1, 12, 8, 0, 20, tzinfo=UTC),
        datetime(2026, 1, 12, 8, 45, 20, tzinfo=UTC),
    ]
    assert rule.times_of_day() == (time(8, 0, 20, tzinfo=UTC), time(8, 45, 20, tzinfo=UTC))


def test_rrule_22_bysetpos_counts_times_of_day_within_the_period() -> None:
    rule = Rule.parse("FREQ=MONTHLY;BYDAY=MO;BYHOUR=9,17;BYSETPOS=-1;COUNT=2", dtstart=START)
    assert list(occurrences(rule)) == [datetime(2026, 1, 26, 17), datetime(2026, 2, 23, 17)]


def test_time_parts_are_written_and_described() -> None:
    rule = Rule.parse("FREQ=DAILY;BYMINUTE=30;BYHOUR=17,9", dtstart=START)
    assert rule.to_text() == "FREQ=DAILY;BYHOUR=17,9;BYMINUTE=30"
    assert Rule.parse(rule.to_text(), dtstart=START) == rule
    assert describe(rule) == "daily at 09:30 and 17:30"
    seconds = Rule.parse("FREQ=DAILY;BYSECOND=0,30", dtstart=START)
    assert describe(seconds) == "daily at 10:00:00 and 10:00:30"
