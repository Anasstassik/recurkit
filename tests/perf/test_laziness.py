import tracemalloc
from collections.abc import Iterator
from datetime import datetime
from itertools import islice

import pytest

from recurkit import RecurrenceSet, Rule
from recurkit.expand import (
    ExpandedPeriods,
    after,
    before,
    between,
    count_expanded_periods,
    occurrences,
)
from recurkit.timezones import FakeProvider

pytestmark = pytest.mark.perf


@pytest.fixture
def periods() -> Iterator[ExpandedPeriods]:
    with count_expanded_periods() as counter:
        yield counter


def test_first_values_of_an_infinite_rule_need_little_memory() -> None:
    rule = Rule.parse("FREQ=DAILY;BYMONTH=1,7", datetime(2000, 1, 1, 9))
    tracemalloc.start()
    try:
        first = list(islice(occurrences(rule), 10))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(first) == 10
    assert peak < 64 * 1024


@pytest.mark.parametrize(
    ("text", "max_periods"),
    [
        ("FREQ=DAILY", 32),
        ("FREQ=WEEKLY;BYDAY=MO,FR", 6),
        ("FREQ=MONTHLY;BYDAY=-1FR", 2),
        ("FREQ=DAILY;BYMONTH=6;BYDAY=SA", 32),
        ("FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29", 2),
    ],
)
def test_window_query_far_from_dtstart_expands_only_the_window(
    periods: ExpandedPeriods, text: str, max_periods: int
) -> None:
    rule = Rule.parse(text, datetime(1900, 1, 1, 9))
    found = list(between(rule, datetime(2026, 6, 1), datetime(2026, 7, 1)))
    assert 1 <= periods.count <= max_periods
    assert all(datetime(2026, 6, 1) <= value <= datetime(2026, 7, 1) for value in found)


def test_zoned_set_window_query_far_from_dtstart(periods: ExpandedPeriods) -> None:
    rule = Rule.parse("FREQ=DAILY", datetime(2000, 3, 1, 3, 30), "Fake/EasternEurope")
    rset = RecurrenceSet(rule, provider=FakeProvider())
    window = list(rset.between(datetime(2026, 3, 1), datetime(2026, 4, 1)))
    assert 1 <= periods.count <= 34
    assert len(window) == 30


def test_counter_sees_the_walk_from_dtstart_and_nests() -> None:
    rule = Rule.parse("FREQ=DAILY;COUNT=10", datetime(2026, 1, 1, 9))
    with count_expanded_periods() as outer:
        list(occurrences(rule))
        with count_expanded_periods() as inner:
            assert before(rule, datetime(2026, 1, 4)) == datetime(2026, 1, 3, 9)
    assert inner.count == 4
    assert outer.count == 10 + 4
    list(occurrences(rule))
    assert outer.count == 14


def test_h6_before_far_from_dtstart_expands_only_nearby_periods(periods: ExpandedPeriods) -> None:
    rset = RecurrenceSet(Rule.parse("FREQ=DAILY", datetime(1900, 1, 1, 9)))
    assert rset.before(datetime(2026, 6, 15)) == datetime(2026, 6, 14, 9)
    assert periods.count <= 32


@pytest.mark.parametrize(
    ("text", "max_periods"),
    [
        ("FREQ=DAILY", 16),
        ("FREQ=WEEKLY;BYDAY=MO,FR", 6),
        ("FREQ=MONTHLY;BYDAY=-1FR", 8),
        ("FREQ=YEARLY;INTERVAL=4;BYMONTH=11;BYDAY=TU;BYMONTHDAY=2,3,4,5,6,7,8", 4),
    ],
)
def test_before_and_after_far_from_dtstart_stay_within_budget(
    periods: ExpandedPeriods, text: str, max_periods: int
) -> None:
    rule = Rule.parse(text, datetime(1900, 1, 1, 9))
    rset = RecurrenceSet(
        Rule.parse(text, datetime(1900, 1, 1, 9), "Fake/EasternEurope"), provider=FakeProvider()
    )
    moment = datetime(2026, 6, 15)
    for query in (before, after):
        periods.count = 0
        assert query(rule, moment) is not None
        assert periods.count <= max_periods, query.__name__
    for method in (rset.before, rset.after):
        periods.count = 0
        assert method(moment) is not None
        assert periods.count <= max_periods + 2, method.__name__
