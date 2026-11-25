from datetime import UTC, date, datetime

import pytest

from recurkit import RuleSyntaxError, RuleValidationError
from recurkit.calendar_math import Weekday
from recurkit.rule import Frequency, WeekdayNum, parse_date_or_datetime, parse_rrule


def test_parse_full_rule() -> None:
    rule = parse_rrule(
        "FREQ=MONTHLY;INTERVAL=2;COUNT=10;BYMONTH=1,-12;BYMONTHDAY=+1,-1;"
        "BYDAY=2TU,-1FR,MO;BYSETPOS=-1;WKST=SU"
    )
    assert rule.freq is Frequency.MONTHLY
    assert rule.interval == 2
    assert rule.count == 10
    assert rule.by_month == (1, -12)
    assert rule.by_month_day == (1, -1)
    assert rule.by_day == (
        WeekdayNum(Weekday.TU, 2),
        WeekdayNum(Weekday.FR, -1),
        WeekdayNum(Weekday.MO),
    )
    assert rule.by_set_pos == (-1,)
    assert rule.wkst is Weekday.SU


def test_rrule_03_parts_in_any_order_and_any_case() -> None:
    a = parse_rrule("RRULE:freq=weekly;byday=tu,th;interval=2")
    b = parse_rrule("INTERVAL=2;BYDAY=TU,TH;FREQ=WEEKLY;")
    assert a == b
    assert a.by_day == (WeekdayNum(Weekday.TU), WeekdayNum(Weekday.TH))


def test_until_in_date_datetime_and_utc_forms() -> None:
    assert parse_rrule("FREQ=DAILY;UNTIL=20261231").until == date(2026, 12, 31)
    assert parse_rrule("FREQ=DAILY;UNTIL=20261231T235959").until == datetime(
        2026, 12, 31, 23, 59, 59
    )
    utc = parse_rrule("FREQ=DAILY;UNTIL=20261231T220000Z").until
    assert utc == datetime(2026, 12, 31, 22, tzinfo=UTC)
    assert parse_date_or_datetime("20240229") == date(2024, 2, 29)
    for bad in ("20260230", "20261231T246000", "2026-12-31", "20261231T235960"):
        with pytest.raises(ValueError):
            parse_date_or_datetime(bad)


def test_dt_03_utc_offset_form_is_rejected() -> None:
    with pytest.raises(RuleValidationError) as info:
        parse_rrule("FREQ=DAILY;UNTIL=19980119T230000-0800")
    assert info.value.requirement_id == "DT-03"


def test_rrule_02_duplicate_part_is_rejected() -> None:
    with pytest.raises(RuleSyntaxError, match="RRULE-02") as info:
        parse_rrule("FREQ=DAILY;COUNT=2;COUNT=3")
    assert info.value.position == 19
    assert "FREQ=DAILY;COUNT=2;COUNT=3"[19:] == "COUNT=3"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty rule"),
        ("FREQ=DAILY;;COUNT=2", "empty rule part"),
        ("FREQ=DAILY;COUNT", "has no '='"),
        ("FREQ=DAILY;COUNT=", "empty value"),
        ("FREQ=DAILY;FOO=1", "unknown rule part"),
        ("FREQ=HOURLY", "not supported"),
        ("FREQ=SOMETIMES", "unknown FREQ"),
        ("FREQ=DAILY;BYHOUR=10", "not supported"),
        ("FREQ=DAILY;COUNT=-1", "not a number"),
        ("FREQ=DAILY;BYMONTH=1,,2", "not an integer"),
        ("FREQ=DAILY;BYDAY=XX", "not a weekday"),
        ("FREQ=DAILY;WKST=1", "not a weekday"),
        ("FREQ=DAILY;UNTIL=tomorrow", "UNTIL"),
    ],
)
def test_syntax_errors_are_reported(text: str, message: str) -> None:
    with pytest.raises(RuleSyntaxError, match=message):
        parse_rrule(text)


def test_rrule_01_freq_is_required() -> None:
    with pytest.raises(RuleValidationError) as info:
        parse_rrule("COUNT=3;BYDAY=MO")
    assert info.value.requirement_id == "RRULE-01"
    with pytest.raises(RuleValidationError) as zero:
        parse_rrule("FREQ=MONTHLY;BYDAY=0MO")
    assert zero.value.requirement_id == "RRULE-06"


@pytest.mark.parametrize(
    "text",
    [
        "FREQ=DAILY;COUNT=\u0663",
        "FREQ=DAILY;INTERVAL=\uff12",
        "FREQ=DAILY;UNTIL=\uff12\uff10\uff12\uff16\uff10\uff11\uff10\uff15",
        "FREQ=YEARLY;BYMONTH=1\n,2",
        "FREQ=MONTHLY;BYDAY=\u0662TU",
        "FREQ=DAILY;COUNT=3\n;WKST=MO",
    ],
    ids=[
        "arabic-indic-3",
        "fullwidth-2",
        "fullwidth-until",
        "newline-before-comma",
        "arabic-indic-ordinal",
        "newline-at-the-end-of-a-value",
    ],
)
def test_h2_values_outside_the_ascii_grammar_are_rejected(text: str) -> None:
    with pytest.raises(RuleSyntaxError):
        parse_rrule(text)


@pytest.mark.parametrize(
    "value", ["\uff12\uff10\uff12\uff16\uff10\uff11\uff10\uff15", "2026010\u0665"]
)
def test_date_values_accept_only_ascii_digits(value: str) -> None:
    with pytest.raises(ValueError, match="not a DATE"):
        parse_date_or_datetime(value)
