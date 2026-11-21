from datetime import datetime, timedelta

from dateutil.rrule import rrulestr
from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Rule
from recurkit.expand import occurrences
from tests.strategies import dtstarts, rule_texts

HORIZON = timedelta(days=4 * 366)
LIMIT = 40


def _assert_same(text: str, dtstart: datetime) -> None:
    rule = Rule.parse(text, dtstart=dtstart)
    cutoff = dtstart + HORIZON
    ours = []
    for value in occurrences(rule, until=cutoff):
        ours.append(value)
        if len(ours) == LIMIT:
            break
    reference = rrulestr(text, dtstart=dtstart).between(dtstart, cutoff, inc=True)[:LIMIT]
    assert ours == reference, text


@settings(max_examples=200, deadline=None)
@given(text=st.one_of(rule_texts("DAILY"), rule_texts("WEEKLY")), dtstart=dtstarts)
def test_daily_and_weekly_match_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)


@settings(max_examples=200, deadline=None)
@given(text=rule_texts("MONTHLY"), dtstart=dtstarts)
def test_monthly_matches_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)


@settings(max_examples=200, deadline=None)
@given(text=rule_texts("YEARLY"), dtstart=dtstarts)
def test_yearly_matches_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)
