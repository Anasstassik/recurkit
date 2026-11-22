from datetime import datetime, timedelta

from dateutil.rrule import rrulestr
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from recurkit import Frequency, Rule
from recurkit.expand import occurrences
from tests.strategies import dtstarts, numbered_yearly_rule_texts, rule_texts

HORIZON = timedelta(days=4 * 366)
LIMIT = 40


def _assert_same(text: str, dtstart: datetime) -> None:
    rule = Rule.parse(text, dtstart=dtstart)
    if rule.freq is Frequency.WEEKLY and rule.by_set_pos:
        dtstart -= timedelta(days=(dtstart.weekday() - rule.wkst) % 7)
        rule = Rule.parse(text, dtstart=dtstart)
    cutoff = dtstart + HORIZON
    ours = []
    for value in occurrences(rule, until=cutoff):
        ours.append(value)
        if len(ours) == LIMIT:
            break
    assume(ours)
    reference = list(rrulestr(text, dtstart=dtstart).replace(until=cutoff))[:LIMIT]
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


FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")


@settings(max_examples=300, deadline=None)
@given(
    text=st.sampled_from(FREQUENCIES).flatmap(lambda f: rule_texts(f, set_pos=True)),
    dtstart=dtstarts,
)
def test_rrule_22_by_set_pos_matches_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)


@settings(max_examples=200, deadline=None)
@given(
    text=st.sampled_from(("WEEKLY", "MONTHLY", "YEARLY")).flatmap(
        lambda f: rule_texts(f, set_pos=True, wkst=True)
    ),
    dtstart=dtstarts,
)
def test_rrule_21_wkst_matches_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)


@settings(max_examples=150, deadline=None)
@given(text=numbered_yearly_rule_texts(), dtstart=dtstarts)
def test_rrule_26_by_week_no_and_by_year_day_match_dateutil(text: str, dtstart: datetime) -> None:
    _assert_same(text, dtstart)
