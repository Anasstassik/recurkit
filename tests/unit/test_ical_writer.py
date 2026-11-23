from datetime import UTC, date, datetime

import pytest

from recurkit import RecurrenceSet, Rule, parse_ics
from recurkit.ical import (
    escape_text,
    fold,
    format_calendar,
    format_content_line,
    format_event,
    format_recurrence,
    parse_content_line,
    parse_recurrence,
    unescape_text,
    unfold,
)
from recurkit.timezones import FakeProvider


def test_ical_01_fold_at_75_octets_and_unfold_restores() -> None:
    line = "RDATE:" + ",".join(f"2026{m:02d}01T090000" for m in range(1, 13))
    folded = fold(line)
    physical = folded.split("\r\n")
    assert len(physical) > 1
    assert all(len(part.encode()) <= 75 for part in physical)
    assert all(part.startswith(" ") for part in physical[1:])
    assert list(unfold(folded)) == [(1, line)]


def test_ical_01_fold_never_splits_a_multi_octet_character() -> None:
    line = "SUMMARY:" + "Київ" * 40
    physical = fold(line).split("\r\n")
    assert all(len(part.encode()) <= 75 for part in physical)
    assert "".join(p[1:] if i else p for i, p in enumerate(physical)) == line
    assert fold("X:short") == "X:short"


def test_ical_02_parameter_values_are_quoted_when_needed() -> None:
    text = format_content_line("dtstart", "20260101T090000", {"tzid": "Odd;Zone:Name"})
    assert text == 'DTSTART;TZID="Odd;Zone:Name":20260101T090000'
    parsed = parse_content_line(text)
    assert parsed.param("TZID") == "Odd;Zone:Name"
    with pytest.raises(ValueError, match="double quote"):
        format_content_line("X", "1", {"P": 'a"b'})


def test_writes_all_day_floating_and_utc_sets() -> None:
    all_day = RecurrenceSet(
        Rule.parse("FREQ=YEARLY;COUNT=3", date(2026, 1, 1)),
        rdates=[date(2026, 7, 4)],
        exdates=[date(2027, 1, 1)],
    )
    assert format_recurrence(all_day) == (
        "DTSTART;VALUE=DATE:20260101\r\n"
        "RRULE:FREQ=YEARLY;COUNT=3\r\n"
        "RDATE;VALUE=DATE:20260704\r\n"
        "EXDATE;VALUE=DATE:20270101\r\n"
    )
    floating = RecurrenceSet(Rule.parse("FREQ=DAILY;COUNT=2", datetime(2026, 1, 1, 9)))
    assert format_recurrence(floating) == "DTSTART:20260101T090000\r\nRRULE:FREQ=DAILY;COUNT=2\r\n"
    utc = RecurrenceSet(
        Rule.parse("FREQ=DAILY;COUNT=2", datetime(2026, 1, 1, 9, tzinfo=UTC)),
        rdates=[datetime(2026, 2, 1, 9, tzinfo=UTC)],
    )
    assert "RDATE:20260201T090000Z\r\n" in format_recurrence(utc)


def test_zoned_values_keep_the_tzid_except_the_second_pass_of_a_fold() -> None:
    provider = FakeProvider()
    text = (
        "DTSTART;TZID=Fake/EasternEurope:20261020T030000\r\n"
        "RRULE:FREQ=WEEKLY;COUNT=4\r\n"
        "RDATE;TZID=Fake/EasternEurope:20261101T120000\r\n"
        "RDATE:20261025T013000Z\r\n"
        "EXDATE;TZID=Fake/EasternEurope:20261027T030000\r\n"
    )
    rset = parse_recurrence(text, provider=provider)
    written = format_recurrence(rset)
    assert written == text
    again = parse_recurrence(written, provider=provider)
    assert list(again) == list(rset)


RFC_SETS = [
    "DTSTART;TZID=America/New_York:19970902T090000\nRRULE:FREQ=DAILY;COUNT=10\n"
    "RDATE;TZID=America/New_York:19970913T120000\nEXDATE;TZID=America/New_York:19970905T090000",
    "DTSTART;VALUE=DATE:19970101\nRRULE:FREQ=MONTHLY;BYMONTHDAY=13;BYDAY=FR;UNTIL=20001231\nEXDATE:19980213",
    "DTSTART:19970902T090000Z\nRRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;COUNT=8\n"
    "RDATE:19971225T090000Z,19971226T090000Z",
]


@pytest.mark.parametrize("text", RFC_SETS)
def test_round_trip_keeps_occurrences(text: str) -> None:
    rset = parse_recurrence(text.replace("EXDATE:19980213", "EXDATE;VALUE=DATE:19980213"))
    again = parse_recurrence(format_recurrence(rset))
    assert list(again) == list(rset)
    assert again.rule == rset.rule


@pytest.mark.parametrize(
    "text", ["plain", "a;b,c", "back\\slash", "two\nlines", "mixed; all,\nthree \\ two"]
)
def test_ical_03_escape_text_round_trips(text: str) -> None:
    escaped = escape_text(text)
    assert "\n" not in escaped
    assert unescape_text(escaped) == text
    assert escape_text("a;b,c\\d\r\ne") == r"a\;b\,c\\d\ne"


def _single_event(*lines: str) -> str:
    calendar = parse_ics(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:x\nBEGIN:VEVENT\n"
        + "\n".join(lines)
        + "\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    return "\n".join(format_event(calendar.events[0]))


def test_format_event_writes_all_day_duration_and_flags() -> None:
    assert _single_event(
        "UID:a", "DTSTART;VALUE=DATE:20260518", "TRANSP:TRANSPARENT", "STATUS:CANCELLED"
    ) == (
        "BEGIN:VEVENT\nUID:a\nDTSTART;VALUE=DATE:20260518\nDURATION:P1D\n"
        "TRANSP:TRANSPARENT\nSTATUS:CANCELLED\nEND:VEVENT"
    )
    assert _single_event("UID:b", "DTSTART:20260105T090000Z", "SUMMARY:x\\, y") == (
        "BEGIN:VEVENT\nUID:b\nSUMMARY:x\\, y\nDTSTART:20260105T090000Z\nEND:VEVENT"
    )


def test_format_event_keeps_zone_rule_and_moves_fold_end_to_utc() -> None:
    written = _single_event(
        "UID:z",
        "DTSTART;TZID=Europe/Kyiv:20261024T033000",
        "DURATION:P1D",
        "RRULE:FREQ=DAILY;COUNT=2",
        "EXDATE;TZID=Europe/Kyiv:20261025T033000",
    )
    assert "DTSTART;TZID=Europe/Kyiv:20261024T033000" in written
    assert "DURATION:P1D" in written
    assert "RRULE:FREQ=DAILY;COUNT=2" in written
    assert "EXDATE;TZID=Europe/Kyiv:20261025T033000" in written
    folded = _single_event(
        "UID:f",
        "DTSTART;TZID=Europe/Kyiv:20261025T030000",
        "DTEND:20261025T010000Z",
    )
    assert "DTEND:20261025T010000Z" in folded


def test_format_calendar_writes_header_and_folds_long_lines() -> None:
    event = parse_ics(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:x\nBEGIN:VEVENT\nUID:long\n"
        "DTSTART:20260105T090000\nSUMMARY:" + "слово " * 30 + "\nEND:VEVENT\nEND:VCALENDAR\n"
    ).events[0]
    text = format_calendar([event])
    lines = text.split("\r\n")
    assert lines[:3] == ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RecurKit//RecurKit//EN"]
    assert lines[-2:] == ["END:VCALENDAR", ""]
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert parse_ics(text).events[0].summary == event.summary
