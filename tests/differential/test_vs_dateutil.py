from datetime import datetime, timedelta
from itertools import islice

import pytest
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


@pytest.mark.parametrize("wkst", ["MO", "TU", "WE", "TH", "FR", "SA", "SU"])
def test_weekly_rules_at_the_start_of_the_calendar_match_dateutil(wkst: str) -> None:
    for by in ("", ";BYDAY=SU,MO,SA", ";INTERVAL=2;BYDAY=TU,FR"):
        text = f"FREQ=WEEKLY;WKST={wkst}{by}"
        for day in (1, 3, 6):
            dtstart = datetime(1, 1, day, 9)
            ours = list(islice(occurrences(Rule.parse(text, dtstart=dtstart)), 8))
            assert ours == list(islice(rrulestr(text, dtstart=dtstart), 8)), (text, day)
        last = list(occurrences(Rule.parse(text + ";COUNT=9", dtstart=datetime(9999, 12, 1, 9))))
        assert last and last[-1].year == 9999


time_parts = st.fixed_dictionaries(
    {},
    optional={
        "BYHOUR": st.lists(st.integers(0, 23), min_size=1, max_size=3),
        "BYMINUTE": st.lists(st.integers(0, 59), min_size=1, max_size=3),
        "BYSECOND": st.lists(st.integers(0, 59), min_size=1, max_size=2),
    },
).map(lambda parts: "".join(f";{k}={','.join(map(str, v))}" for k, v in parts.items()))


@settings(max_examples=200, deadline=None)
@given(
    text=st.sampled_from(FREQUENCIES).flatmap(lambda f: rule_texts(f, set_pos=True)),
    times=time_parts,
    dtstart=dtstarts,
)
def test_rrule_29_times_of_day_match_dateutil(text: str, times: str, dtstart: datetime) -> None:
    _assert_same(text + times, dtstart)


SUB_DAILY = ("HOURLY", "MINUTELY", "SECONDLY")
SUB_DAILY_HORIZON = {
    Frequency.HOURLY: timedelta(days=40),
    Frequency.MINUTELY: timedelta(days=1),
    Frequency.SECONDLY: timedelta(minutes=30),
}


@settings(max_examples=200, deadline=None)
@given(
    text=st.sampled_from(SUB_DAILY).flatmap(lambda f: rule_texts(f, set_pos=True)),
    times=time_parts,
    dtstart=dtstarts,
)
def test_rrule_30_sub_daily_rules_match_dateutil(text: str, times: str, dtstart: datetime) -> None:
    rule = Rule.parse(text + times, dtstart=dtstart)
    cutoff = dtstart + SUB_DAILY_HORIZON[rule.freq]
    ours = list(islice(occurrences(rule, until=cutoff), LIMIT))
    assume(ours)
    reference = list(rrulestr(text + times, dtstart=dtstart).replace(until=cutoff))[:LIMIT]
    assert ours == reference, text + times
