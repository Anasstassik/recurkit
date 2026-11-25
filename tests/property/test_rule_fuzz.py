from datetime import UTC, date, datetime

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from recurkit import RecurKitError, Rule, RuleSyntaxError, Weekday, WeekdayNum
from recurkit.rule import Frequency, parse_rrule
from tests.strategies import rule_texts

TOKENS = [
    "FREQ=", "DAILY", "WEEKLY", "MONTHLY", "YEARLY", "HOURLY", "INTERVAL=", "COUNT=",
    "UNTIL=", "BYMONTH=", "BYMONTHDAY=", "BYDAY=", "BYSETPOS=", "WKST=", "BYHOUR=",
    "BYWEEKNO=", "BYYEARDAY=",
    "MO", "TU", "-1FR", "2TU", "+3", "-0", "0", "1", "12", "31", "366", "99999999999",
    "20261231", "20261231T235959", "20260230", "T", "Z", ";", ",", "=", " ", "RRULE:",
]


@settings(max_examples=300)
@given(text=st.text(max_size=60))
def test_arbitrary_text_gives_rule_or_library_error(text: str) -> None:
    try:
        rule = Rule.parse(text, dtstart=datetime(2026, 1, 1, 9))
    except RecurKitError:
        return
    assert isinstance(rule, Rule)


@settings(max_examples=300)
@given(pieces=st.lists(st.sampled_from(TOKENS), max_size=14))
def test_token_soup_gives_rule_or_library_error(pieces: list[str]) -> None:
    try:
        rule = Rule.parse("".join(pieces), dtstart=date(2026, 1, 1))
    except RecurKitError:
        return
    assert rule.to_text().startswith("FREQ=")


ints = st.integers
weekday_nums = st.builds(
    WeekdayNum,
    st.sampled_from(list(Weekday)),
    st.one_of(st.none(), ints(1, 53), ints(-53, -1)),
)
untils = st.one_of(
    st.none(),
    st.dates(date(1900, 1, 1), date(2100, 12, 31)),
    st.datetimes(datetime(1900, 1, 1), datetime(2100, 1, 1)).map(
        lambda d: d.replace(microsecond=0)
    ),
    st.datetimes(datetime(1900, 1, 1), datetime(2100, 1, 1)).map(
        lambda d: d.replace(microsecond=0, tzinfo=UTC)
    ),
)
rules = st.builds(
    Rule,
    freq=st.sampled_from(list(Frequency)),
    interval=ints(1, 1000),
    count=st.one_of(st.none(), ints(1, 10_000)),
    until=untils,
    by_month=st.lists(ints(1, 12), max_size=3).map(tuple),
    by_week_no=st.lists(st.one_of(ints(1, 53), ints(-53, -1)), max_size=2).map(tuple),
    by_year_day=st.lists(st.one_of(ints(1, 366), ints(-366, -1)), max_size=2).map(tuple),
    by_month_day=st.lists(st.one_of(ints(1, 31), ints(-31, -1)), max_size=3).map(tuple),
    by_day=st.lists(weekday_nums, max_size=3).map(tuple),
    by_set_pos=st.lists(st.one_of(ints(1, 366), ints(-366, -1)), max_size=2).map(tuple),
    wkst=st.sampled_from(list(Weekday)),
)


@given(rule=rules)
def test_to_text_roundtrips_through_parser(rule: Rule) -> None:
    assert parse_rrule(rule.to_text()) == rule


FOREIGN_DIGITS = ("\u0663", "\uff12", "\u0967", "\u09e9", "\u1813")
valid_texts = st.tuples(
    st.sampled_from(("DAILY", "WEEKLY", "MONTHLY", "YEARLY")).flatmap(rule_texts),
    st.integers(1, 500),
).map(lambda pair: f"{pair[0]};COUNT={pair[1]}")


@given(text=valid_texts, pick=st.integers(0, 1000), digit=st.sampled_from(FOREIGN_DIGITS))
def test_a_digit_from_another_script_makes_a_valid_rule_a_syntax_error(
    text: str, pick: int, digit: str
) -> None:
    try:
        parse_rrule(text)
    except RecurKitError:
        assume(False)
    positions = [i for i, char in enumerate(text) if char.isascii() and char.isdigit()]
    at = positions[pick % len(positions)]
    try:
        parse_rrule(text[:at] + digit + text[at + 1 :])
    except RuleSyntaxError:
        return
    raise AssertionError(f"accepted {text[:at] + digit + text[at + 1 :]!r}")
