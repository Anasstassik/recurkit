from datetime import UTC, date, datetime, timedelta
from itertools import islice

import pytest

from recurkit import Frequency, RecurrenceSet, Rule, RuleValidationError, describe
from recurkit.expand import after, between, count_expanded_periods, occurrences

START = datetime(2026, 1, 5, 9, 7, 3)


def _texts(text: str, n: int = 4, start: datetime = START) -> list[str]:
    return [f"{v:%m-%d %H:%M:%S}" for v in islice(occurrences(Rule.parse(text, dtstart=start)), n)]


def test_rrule_30_sub_daily_frequencies_parse_and_write_back() -> None:
    for freq in ("HOURLY", "MINUTELY", "SECONDLY"):
        rule = Rule.parse(f"FREQ={freq};INTERVAL=2", dtstart=START)
        assert rule.freq is Frequency(freq)
        assert rule.to_text() == f"FREQ={freq};INTERVAL=2"
    with pytest.raises(RuleValidationError, match="RRULE-28"):
        Rule.parse("FREQ=HOURLY", dtstart=date(2026, 1, 5))


def test_rrule_30_time_parts_expand_finer_and_limit_coarser_units() -> None:
    assert _texts("FREQ=HOURLY;INTERVAL=3;BYMINUTE=0,30") == [
        "01-05 09:30:03",
        "01-05 12:00:03",
        "01-05 12:30:03",
        "01-05 15:00:03",
    ]
    assert _texts("FREQ=MINUTELY;BYHOUR=10;BYSECOND=0,30", 3) == [
        "01-05 10:00:00",
        "01-05 10:00:30",
        "01-05 10:01:00",
    ]
    assert _texts("FREQ=SECONDLY;INTERVAL=20;BYMINUTE=8", 3) == [
        "01-05 09:08:03",
        "01-05 09:08:23",
        "01-05 09:08:43",
    ]


def test_rrule_30_day_parts_limit_and_skip_whole_days() -> None:
    rule = Rule.parse("FREQ=MINUTELY;INTERVAL=15;BYDAY=SA;BYHOUR=8", dtstart=START)
    with count_expanded_periods() as work:
        values = list(islice(occurrences(rule), 5))
    assert [f"{v:%a %H:%M}" for v in values] == [
        "Sat 08:07",
        "Sat 08:22",
        "Sat 08:37",
        "Sat 08:52",
        "Sat 08:07",
    ]
    assert values[4] - values[0] == timedelta(days=7)
    assert work.count < 200


def test_rrule_22_bysetpos_picks_within_one_hour() -> None:
    assert _texts("FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSETPOS=-1;COUNT=3") == [
        "01-05 09:45:03",
        "01-05 10:45:03",
        "01-05 11:45:03",
    ]


def test_window_queries_jump_to_the_window_of_a_sub_daily_rule() -> None:
    rule = Rule.parse("FREQ=MINUTELY;INTERVAL=7", dtstart=START)
    low = datetime(2027, 3, 1, 12)
    with count_expanded_periods() as work:
        window = list(between(rule, low, low + timedelta(minutes=21)))
    assert window == [
        datetime(2027, 3, 1, 12, 2, 3),
        datetime(2027, 3, 1, 12, 9, 3),
        datetime(2027, 3, 1, 12, 16, 3),
    ]
    assert work.count < 10
    assert after(rule, low) == window[0]


def test_utc_and_zoned_sub_daily_series() -> None:
    utc = Rule.parse("FREQ=HOURLY;COUNT=2", dtstart=START.replace(tzinfo=UTC))
    assert [v.utcoffset() for v in RecurrenceSet(utc)] == [timedelta(0), timedelta(0)]  # type: ignore[union-attr]
    zoned = Rule.parse("FREQ=HOURLY;INTERVAL=12;COUNT=2", dtstart=START, tzid="Europe/Kyiv")
    assert [f"{v:%H:%M}" for v in RecurrenceSet(zoned)] == ["09:07", "21:07"]


def test_sub_daily_rules_are_described() -> None:
    rule = Rule.parse("FREQ=MINUTELY;INTERVAL=20;BYHOUR=9,10", dtstart=datetime(2026, 1, 5, 9))
    assert describe(rule) == "every 20 minutes in hours 9 and 10 from 09:00"
    assert describe(Rule.parse("FREQ=HOURLY", dtstart=START)) == "hourly from 09:07"
