from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from recurkit import RuleValidationError
from recurkit.calendar_math import Weekday
from recurkit.rule import Frequency, Rule, RuleParts, WeekdayNum


def test_rule_defaults_and_immutability() -> None:
    rule = RuleParts(Frequency.DAILY)
    assert rule.interval == 1
    assert rule.wkst is Weekday.MO
    assert rule.count is None and rule.until is None
    assert rule.is_infinite
    with pytest.raises(AttributeError):
        rule.interval = 2  # type: ignore[misc]


def test_rule_converts_lists_to_tuples_and_is_hashable() -> None:
    rule = RuleParts(
        "MONTHLY",  # type: ignore[arg-type]
        by_month=[1, 6],  # type: ignore[arg-type]
        by_day=[WeekdayNum(Weekday.TU, 2)],  # type: ignore[arg-type]
    )
    assert rule.freq is Frequency.MONTHLY
    assert rule.by_month == (1, 6)
    assert rule.has_by_parts and rule.has_numeric_by_day
    assert hash(rule) == hash(RuleParts(Frequency.MONTHLY, by_month=(1, 6), by_day=rule.by_day))


def test_weekday_num_text_and_zero_ordinal() -> None:
    assert WeekdayNum(Weekday.TU, 2).to_text() == "2TU"
    assert str(WeekdayNum(Weekday.FR, -1)) == "-1FR"
    assert WeekdayNum(Weekday.MO).to_text() == "MO"
    assert not WeekdayNum(Weekday.MO).is_numeric
    with pytest.raises(ValueError, match="zero"):
        WeekdayNum(Weekday.MO, 0)


def test_rule_dtstart_kinds() -> None:
    assert Rule(Frequency.YEARLY, dtstart=date(2026, 1, 1)).is_all_day
    timed = Rule(Frequency.YEARLY, dtstart=datetime(2026, 1, 1, 10))
    assert not timed.is_all_day
    assert timed.require_dtstart() == datetime(2026, 1, 1, 10)
    with pytest.raises(ValueError, match="no DTSTART"):
        RuleParts(Frequency.YEARLY).require_dtstart()
    assert Frequency.DAILY.rank < Frequency.WEEKLY.rank < Frequency.YEARLY.rank


def test_rrule_04_to_text_puts_freq_first() -> None:
    rule = RuleParts(
        Frequency.MONTHLY,
        interval=2,
        until=datetime(2026, 12, 31, 22, tzinfo=UTC),
        by_day=(WeekdayNum(Weekday.TU, 2), WeekdayNum(Weekday.FR, -1)),
        by_set_pos=(1,),
        wkst=Weekday.SU,
    )
    text = rule.to_text()
    assert text.startswith("FREQ=MONTHLY;")
    assert (
        text == "FREQ=MONTHLY;INTERVAL=2;UNTIL=20261231T220000Z;BYDAY=2TU,-1FR;BYSETPOS=1;WKST=SU"
    )
    assert str(RuleParts(Frequency.DAILY, until=date(2026, 1, 9))) == "FREQ=DAILY;UNTIL=20260109"


START = datetime(2026, 1, 1, 9)


def test_rule_01_rule_needs_dtstart() -> None:
    with pytest.raises(RuleValidationError, match="RULE-01"):
        Rule(Frequency.YEARLY)
    assert RuleParts(Frequency.YEARLY).dtstart is None


@pytest.mark.parametrize(
    ("parts", "requirement_id"),
    [
        ({"count": 0}, "RRULE-06"),
        ({"interval": 0}, "RRULE-05"),
        ({"by_set_pos": (0,)}, "RRULE-06"),
        ({"count": 2, "until": datetime(2026, 2, 1, 9)}, "RRULE-07"),
    ],
    ids=["count-0", "interval-0", "set-pos-0", "count-and-until"],
)
def test_rule_01_constructor_rejects_what_validate_rejects(
    parts: dict[str, object], requirement_id: str
) -> None:
    with pytest.raises(RuleValidationError) as info:
        Rule(Frequency.DAILY, dtstart=START, **parts)  # type: ignore[arg-type]
    assert info.value.requirement_id == requirement_id


def test_rule_01_replace_checks_the_new_rule() -> None:
    rule = Rule(Frequency.DAILY, count=3, dtstart=START)
    assert replace(rule, count=5).count == 5
    with pytest.raises(RuleValidationError, match="RRULE-07"):
        replace(rule, until=datetime(2026, 2, 1, 9))
