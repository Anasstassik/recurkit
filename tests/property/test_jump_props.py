from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Rule
from recurkit.expand import after, before, between, occurrences
from tests.strategies import dtstarts, rule_texts

any_rule = st.sampled_from(("DAILY", "WEEKLY", "MONTHLY", "YEARLY")).flatmap(
    lambda f: rule_texts(f, set_pos=True, wkst=True)
)


@settings(max_examples=150, deadline=None)
@given(
    text=any_rule,
    dtstart=dtstarts,
    offset=st.integers(-100, 3000),
    length=st.integers(0, 120),
)
def test_p7_jumping_queries_equal_naive_walk(
    text: str, dtstart: datetime, offset: int, length: int
) -> None:
    rule = Rule.parse(text, dtstart=dtstart)
    start = dtstart + timedelta(days=offset, hours=5)
    end = start + timedelta(days=length)
    walk = [v for v in occurrences(rule, until=end) if v >= start]  # type: ignore[operator]
    assert list(between(rule, start, end)) == walk
    following = next((v for v in occurrences(rule, until=end) if v > start), None)  # type: ignore[operator]
    assert after(rule, start, until=end) == following


sub_daily_rule = st.sampled_from(("HOURLY", "MINUTELY", "SECONDLY")).flatmap(
    lambda f: rule_texts(f, set_pos=True)
)
SUB_DAILY_UNIT = {"HOURLY": 3600, "MINUTELY": 60, "SECONDLY": 1}


@settings(max_examples=150, deadline=None)
@given(
    text=sub_daily_rule,
    dtstart=dtstarts,
    offset=st.integers(-50, 5000),
    length=st.integers(0, 300),
)
def test_p7_sub_daily_window_queries_equal_a_walk(
    text: str, dtstart: datetime, offset: int, length: int
) -> None:
    rule = Rule.parse(text, dtstart=dtstart)
    unit = timedelta(seconds=SUB_DAILY_UNIT[rule.freq.value] * rule.interval)
    start = dtstart + unit * offset + timedelta(seconds=1)
    end = start + unit * length
    walk = [v for v in occurrences(rule, until=end) if v >= start]  # type: ignore[operator]
    assert list(between(rule, start, end)) == walk
    following = next((v for v in occurrences(rule, until=end) if v > start), None)  # type: ignore[operator]
    assert after(rule, start, until=end) == following
    earlier = [v for v in occurrences(rule, until=end) if v < end]  # type: ignore[operator]
    assert before(rule, end) == (earlier[-1] if earlier else None)
