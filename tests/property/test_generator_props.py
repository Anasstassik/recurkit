"""Properties P1-P5 of the design document."""

from datetime import datetime, timedelta
from itertools import islice, pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Rule
from recurkit.expand import Occurrence, occurrences
from tests.property.naive import aligned_with_interval, each_day, matches
from tests.strategies import dtstarts, rule_texts

FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
any_rule = st.sampled_from(FREQS).flatmap(lambda f: rule_texts(f, set_pos=True, wkst=True))
no_set_pos = st.sampled_from(FREQS).flatmap(lambda f: rule_texts(f, wkst=True))
WINDOW = timedelta(days=500)


def _within(rule: Rule, end: datetime) -> list[Occurrence]:
    return list(islice(occurrences(rule, until=end), 1000))


@settings(max_examples=150, deadline=None)
@given(text=any_rule, dtstart=dtstarts)
def test_p1_occurrences_strictly_increase(text: str, dtstart: datetime) -> None:
    values = _within(Rule.parse(text, dtstart=dtstart), dtstart + WINDOW)
    assert all(a < b for a, b in pairwise(values))  # type: ignore[operator]


@settings(max_examples=150, deadline=None)
@given(text=no_set_pos, dtstart=dtstarts)
def test_p2_generator_matches_independent_definition(text: str, dtstart: datetime) -> None:
    rule = Rule.parse(text, dtstart=dtstart)
    last = (dtstart + WINDOW).date()
    expected = {
        d
        for d in each_day(dtstart.date(), last)
        if matches(rule, d) and aligned_with_interval(rule, d)
    }
    end = datetime.combine(last, dtstart.time())
    actual = {value.date() for value in occurrences(rule, until=end)}  # type: ignore[union-attr]
    assert actual == expected


@settings(max_examples=150, deadline=None)
@given(text=any_rule, dtstart=dtstarts, n=st.integers(1, 30))
def test_p3_count_gives_first_n_occurrences(text: str, dtstart: datetime, n: int) -> None:
    unbounded = Rule.parse(text, dtstart=dtstart)
    counted = Rule.parse(f"{text};COUNT={n}", dtstart=dtstart)
    horizon = dtstart + timedelta(days=3660)
    assert list(occurrences(counted, until=horizon)) == _within(unbounded, horizon)[:n]


@settings(max_examples=150, deadline=None)
@given(text=any_rule, dtstart=dtstarts, days=st.integers(0, 600))
def test_p4_until_is_an_inclusive_filter(text: str, dtstart: datetime, days: int) -> None:
    until = dtstart + timedelta(days=days)
    bounded = Rule.parse(f"{text};UNTIL={until:%Y%m%dT%H%M%S}", dtstart=dtstart)
    expected = _within(Rule.parse(text, dtstart=dtstart), until)
    assert list(occurrences(bounded)) == expected
    assert all(v <= until for v in expected)  # type: ignore[operator]


@settings(max_examples=100, deadline=None)
@given(dtstart=dtstarts, k=st.integers(1, 40))
def test_p5_daily_interval_is_every_kth_day(dtstart: datetime, k: int) -> None:
    every = list(islice(occurrences(Rule.parse("FREQ=DAILY", dtstart=dtstart)), 20 * k))
    stepped = list(islice(occurrences(Rule.parse(f"FREQ=DAILY;INTERVAL={k}", dtstart=dtstart)), 20))
    assert stepped == every[::k]
