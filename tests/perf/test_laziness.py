import tracemalloc
from collections.abc import Callable, Iterator
from datetime import date, datetime
from itertools import islice

import pytest

from recurkit import RecurrenceSet, Rule
from recurkit.expand import between, jump, occurrences
from recurkit.timezones import FakeProvider

pytestmark = pytest.mark.perf


@pytest.fixture
def period_counter(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls = [0]
    original: Callable[..., Iterator[date]] = jump.period_occurrences

    def counting(*args: object) -> Iterator[date]:
        calls[0] += 1
        return original(*args)

    monkeypatch.setattr(jump, "period_occurrences", counting)
    return calls


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
    period_counter: list[int], text: str, max_periods: int
) -> None:
    rule = Rule.parse(text, datetime(1900, 1, 1, 9))
    found = list(between(rule, datetime(2026, 6, 1), datetime(2026, 7, 1)))
    assert 1 <= period_counter[0] <= max_periods
    assert all(datetime(2026, 6, 1) <= value <= datetime(2026, 7, 1) for value in found)


def test_zoned_set_window_query_far_from_dtstart(period_counter: list[int]) -> None:
    rule = Rule.parse("FREQ=DAILY", datetime(2000, 3, 1, 3, 30), "Fake/EasternEurope")
    rset = RecurrenceSet(rule, provider=FakeProvider())
    window = list(rset.between(datetime(2026, 3, 1), datetime(2026, 4, 1)))
    assert 1 <= period_counter[0] <= 34
    assert len(window) == 30
