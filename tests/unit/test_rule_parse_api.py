from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from recurkit import Frequency, Rule, RuleSyntaxError, RuleValidationError, Weekday, WeekdayNum


def test_rule_parse_design_document_example() -> None:
    rule = Rule.parse(
        "FREQ=MONTHLY;BYDAY=2TU;COUNT=6", dtstart=datetime(2026, 1, 6, 10, 0), tzid="Europe/Kyiv"
    )
    assert rule.freq is Frequency.MONTHLY
    assert rule.by_day == (WeekdayNum(Weekday.TU, 2),)
    assert rule.count == 6
    assert rule.dtstart == datetime(2026, 1, 6, 10, 0)
    assert rule.tzid == "Europe/Kyiv"


def test_rule_parse_raises_syntax_and_validation_errors() -> None:
    with pytest.raises(RuleSyntaxError):
        Rule.parse("FREQ=DAILY;BYHOUR=9", dtstart=datetime(2026, 1, 1))
    with pytest.raises(RuleValidationError) as info:
        Rule.parse("FREQ=DAILY;COUNT=2;UNTIL=20260105T000000", dtstart=datetime(2026, 1, 1))
    assert info.value.requirement_id == "RRULE-07"


@pytest.mark.parametrize(
    ("dtstart", "tzid", "requirement_id"),
    [
        (datetime(2026, 1, 1, 9, tzinfo=UTC), "Europe/Kyiv", "DT-02"),
        (datetime(2026, 1, 1, 9, tzinfo=timezone(timedelta(hours=-8))), None, "DT-03"),
        (date(2026, 1, 1), "Europe/Kyiv", "DT-04"),
        (datetime(2026, 1, 1, 9), " ", "TZ-04"),
    ],
)
def test_dt_02_dt_03_dt_04_tzid_combinations(
    dtstart: date | datetime, tzid: str | None, requirement_id: str
) -> None:
    with pytest.raises(RuleValidationError) as info:
        Rule.parse("FREQ=DAILY", dtstart=dtstart, tzid=tzid)
    assert info.value.requirement_id == requirement_id
