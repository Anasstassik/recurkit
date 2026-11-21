from datetime import UTC, date, datetime, timedelta
from itertools import islice

import pytest

from recurkit import ICalParseError, RuleSyntaxError, RuleValidationError
from recurkit.ical import parse_recurrence
from recurkit.timezones import FakeProvider


def _walls(values: list[object]) -> list[datetime]:
    return [v.replace(tzinfo=None) for v in values]  # type: ignore[attr-defined]


def test_dt_01_three_forms_of_dtstart() -> None:
    floating = parse_recurrence("DTSTART:20260101T090000\nRRULE:FREQ=DAILY;COUNT=2")
    assert list(floating) == [datetime(2026, 1, 1, 9), datetime(2026, 1, 2, 9)]
    utc = parse_recurrence("DTSTART:20260101T090000Z\nRRULE:FREQ=DAILY;COUNT=1")
    assert list(utc) == [datetime(2026, 1, 1, 9, tzinfo=UTC)]
    zoned = parse_recurrence("DTSTART;TZID=Europe/Kyiv:20260101T090000\nRRULE:FREQ=DAILY;COUNT=1")
    (value,) = list(zoned)
    assert value.utcoffset() == timedelta(hours=2)  # type: ignore[union-attr]
    assert zoned.tzid == "Europe/Kyiv"


def test_design_document_example_with_rdate_and_exdate_lists() -> None:
    text = """DTSTART;TZID=Europe/Kyiv:20260106T100000
RRULE:FREQ=MONTHLY;BYDAY=2TU;COUNT=6
EXDATE;TZID=Europe/Kyiv:20260310T100000,20260414T100000
RDATE;TZID=Europe/Kyiv:20260320T120000
RDATE:20260701T070000Z
SUMMARY:Planning\\, monthly"""
    assert _walls(list(parse_recurrence(text))) == [
        datetime(2026, 1, 13, 10),
        datetime(2026, 2, 10, 10),
        datetime(2026, 3, 20, 12),
        datetime(2026, 5, 12, 10),
        datetime(2026, 6, 9, 10),
        datetime(2026, 7, 1, 10),
    ]


def test_all_day_series_and_values_in_another_zone() -> None:
    all_day = parse_recurrence(
        "DTSTART;VALUE=DATE:20261224\nRRULE:FREQ=YEARLY\nEXDATE;VALUE=DATE:20271224"
    )
    assert list(islice(all_day, 2)) == [date(2026, 12, 24), date(2028, 12, 24)]
    fake = FakeProvider()
    other_zone = parse_recurrence(
        "DTSTART;TZID=Fake/EasternEurope:20260101T100000\n"
        "RRULE:FREQ=DAILY;COUNT=2\n"
        "EXDATE;TZID=Fake/UTC:20260102T080000",
        provider=fake,
    )
    assert _walls(list(other_zone)) == [datetime(2026, 1, 1, 10)]


@pytest.mark.parametrize(
    ("text", "error", "message"),
    [
        ("RRULE:FREQ=DAILY", ICalParseError, "DTSTART is required"),
        ("DTSTART:20260101T090000", ICalParseError, "RRULE is required"),
        (
            "DTSTART:20260101T090000\nDTSTART:20260102T090000\nRRULE:FREQ=DAILY",
            ICalParseError,
            "once",
        ),
        ("DTSTART;VALUE=DATE:20260101T090000\nRRULE:FREQ=DAILY", ICalParseError, "not a DATE"),
        ("DTSTART;VALUE=TEXT:x\nRRULE:FREQ=DAILY", ICalParseError, "VALUE=TEXT"),
        (
            "DTSTART:20260101T090000\nRRULE:FREQ=DAILY\nRDATE;VALUE=PERIOD:x",
            ICalParseError,
            "PERIOD",
        ),
        (
            "DTSTART:20260101T090000\nRRULE:FREQ=DAILY\nRDATE;VALUE=DATE:20260105",
            ICalParseError,
            "same value type",
        ),
        (
            "DTSTART:20260101T090000\nRRULE:FREQ=DAILY\nEXDATE:20260105T090000Z",
            ICalParseError,
            "mix",
        ),
        (
            "DTSTART;TZID=Europe/Kyiv;VALUE=DATE:20260101\nRRULE:FREQ=DAILY",
            RuleValidationError,
            "DT-04",
        ),
        (
            "DTSTART;TZID=Europe/Kyiv:20260101T090000Z\nRRULE:FREQ=DAILY",
            RuleValidationError,
            "DT-02",
        ),
        ("DTSTART:20260101T090000\n\nRRULE:FREQ=DAILY;BYHOUR=9", RuleSyntaxError, "BYHOUR"),
    ],
)
def test_malformed_recurrence_properties(text: str, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        parse_recurrence(text)


def test_rule_errors_name_the_rrule_line() -> None:
    with pytest.raises(RuleValidationError) as info:
        parse_recurrence(
            "DTSTART:20260101T090000\nSUMMARY:x\nRRULE:FREQ=DAILY;COUNT=1;UNTIL=20260102T000000"
        )
    assert info.value.requirement_id == "RRULE-07"
    assert "in RRULE on line 3" in info.value.__notes__
