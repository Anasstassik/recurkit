from datetime import UTC, date, datetime

import pytest

from recurkit import RuleValidationError
from recurkit.rule import Rule, RuleParts, parse_rrule
from recurkit.rule.validation import find_violations, validate


def _requirement(text: str, **kwargs: object) -> str:
    rule = parse_rrule(text, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(RuleValidationError) as info:
        validate(rule)
    return info.value.requirement_id


def test_valid_rule_passes_and_is_returned() -> None:
    rule = parse_rrule("FREQ=MONTHLY;BYDAY=2TU;COUNT=6", dtstart=datetime(2026, 1, 6, 10))
    valid = validate(rule)
    assert isinstance(valid, Rule) and not isinstance(rule, Rule)
    assert valid.to_text() == rule.to_text() and valid.dtstart == rule.dtstart
    assert validate(valid) is valid
    assert find_violations(rule) == []


def test_rrule_05_interval_must_be_positive() -> None:
    assert _requirement("FREQ=DAILY;INTERVAL=0") == "RRULE-05"


@pytest.mark.parametrize(
    "text",
    [
        "FREQ=DAILY;COUNT=0",
        "FREQ=YEARLY;BYMONTH=13",
        "FREQ=YEARLY;BYMONTH=0",
        "FREQ=MONTHLY;BYMONTHDAY=32",
        "FREQ=MONTHLY;BYMONTHDAY=0",
        "FREQ=MONTHLY;BYMONTHDAY=-32",
        "FREQ=MONTHLY;BYDAY=MO;BYSETPOS=367",
        "FREQ=YEARLY;BYDAY=54MO",
    ],
)
def test_rrule_06_values_out_of_range(text: str) -> None:
    assert _requirement(text) == "RRULE-06"


def test_rrule_07_count_and_until_are_exclusive() -> None:
    assert _requirement("FREQ=DAILY;COUNT=3;UNTIL=20261231") == "RRULE-07"


def test_rrule_08_until_type_matches_dtstart() -> None:
    assert _requirement("FREQ=DAILY;UNTIL=20261231", dtstart=datetime(2026, 1, 1, 9)) == "RRULE-08"
    assert _requirement("FREQ=DAILY;UNTIL=20261231T000000", dtstart=date(2026, 1, 1)) == "RRULE-08"
    validate(parse_rrule("FREQ=DAILY;UNTIL=20261231", dtstart=date(2026, 1, 1)))


def test_rrule_09_floating_dtstart_needs_floating_until() -> None:
    text = "FREQ=DAILY;UNTIL=20261231T090000Z"
    assert _requirement(text, dtstart=datetime(2026, 1, 1, 9)) == "RRULE-09"
    validate(parse_rrule("FREQ=DAILY;UNTIL=20261231T090000", dtstart=datetime(2026, 1, 1, 9)))


def test_rrule_10_zoned_dtstart_needs_utc_until() -> None:
    local = datetime(2026, 1, 1, 9)
    text = "FREQ=DAILY;UNTIL=20261231T090000"
    assert _requirement(text, dtstart=local, tzid="Europe/Kyiv") == "RRULE-10"
    assert _requirement(text, dtstart=local.replace(tzinfo=UTC)) == "RRULE-10"
    validate(parse_rrule(text + "Z", dtstart=local, tzid="Europe/Kyiv"))


def test_rrule_13_numeric_by_day_only_monthly_or_yearly() -> None:
    assert _requirement("FREQ=WEEKLY;BYDAY=2TU") == "RRULE-13"
    assert _requirement("FREQ=DAILY;BYDAY=-1FR") == "RRULE-13"
    assert not find_violations(parse_rrule("FREQ=YEARLY;BYDAY=20MO"))
    assert not find_violations(parse_rrule("FREQ=WEEKLY;BYDAY=TU"))


def test_rrule_14_by_month_day_not_with_weekly() -> None:
    assert _requirement("FREQ=WEEKLY;BYMONTHDAY=1") == "RRULE-14"


def test_rrule_15_by_set_pos_needs_another_by_part() -> None:
    assert _requirement("FREQ=MONTHLY;BYSETPOS=-1") == "RRULE-15"
    assert not find_violations(parse_rrule("FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1"))


def test_find_violations_reports_every_problem() -> None:
    rule = RuleParts("WEEKLY", interval=0, count=2, until=date(2026, 1, 1), by_month_day=(1,))  # type: ignore[arg-type]
    ids = [error.requirement_id for error in find_violations(rule)]
    assert ids == ["RRULE-05", "RRULE-07", "RRULE-14"]
