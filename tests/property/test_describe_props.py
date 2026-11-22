from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Rule, describe
from recurkit.rule.describe import MONTH_NAMES, WEEKDAY_NAMES, WORKDAYS
from tests.strategies import rule_texts

FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")


@settings(max_examples=300)
@given(
    text=st.sampled_from(FREQUENCIES).flatmap(lambda f: rule_texts(f, set_pos=True, wkst=True)),
    count=st.integers(2, 500),
)
def test_description_names_every_month_weekday_and_count(text: str, count: int) -> None:
    rule = Rule.parse(f"{text};COUNT={count}", datetime(2026, 1, 1, 8))
    description = describe(rule)
    assert description.endswith(f", {count} times")
    for month in rule.by_month:
        assert MONTH_NAMES[month - 1] in description
    weekdays = {item.weekday for item in rule.by_day}
    if weekdays and weekdays != WORKDAYS and len(weekdays) < 7:
        for weekday in weekdays:
            assert WEEKDAY_NAMES[weekday] in description
