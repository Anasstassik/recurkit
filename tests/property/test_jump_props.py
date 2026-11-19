"""Property P7: queries with arithmetic jumps equal a plain walk from DTSTART."""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Rule
from recurkit.expand import after, between, occurrences
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
