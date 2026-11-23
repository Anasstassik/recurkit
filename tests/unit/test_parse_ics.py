from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from recurkit import Calendar, ICalParseError, RuleValidationError, parse_ics
from recurkit.ical import Duration, Transparency

DATA = Path(__file__).resolve().parents[1] / "data" / "ics"
HEADER = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\n"


def _calendar(*lines: str) -> str:
    return HEADER + "\n".join(lines) + ("\n" if lines else "") + "END:VCALENDAR\n"


def test_parse_ics_reads_the_design_document_example() -> None:
    calendar = parse_ics((DATA / "team.ics").read_text("utf-8"))
    assert calendar.uids == [
        "planning@recurkit.test",
        "offsite@recurkit.test",
        "retro@recurkit.test",
    ]
    (planning,) = calendar.by_uid("planning@recurkit.test")
    starts = list(planning.starts())
    assert [(s.month, s.day, s.hour) for s in starts] == [  # type: ignore[union-attr]
        (1, 13, 10),
        (2, 10, 10),
        (3, 10, 10),
        (4, 14, 10),
        (5, 12, 10),
        (6, 9, 10),
    ]
    assert planning.end_for(starts[3]).utcoffset() == timedelta(hours=3)  # type: ignore[union-attr]
    assert planning.length == Duration(seconds=3600)
    (offsite,) = calendar.by_uid("offsite@recurkit.test")
    assert offsite.summary == "Offsite, Lviv"
    assert (offsite.start, offsite.end) == (date(2026, 5, 18), date(2026, 5, 20))
    assert offsite.transparency is Transparency.TRANSPARENT
    (retro,) = calendar.by_uid("retro@recurkit.test")
    assert retro.cancelled
    assert calendar.by_uid("todo@recurkit.test") == []


def test_ical_07_stream_of_several_calendars_is_merged() -> None:
    text = _calendar("BEGIN:VEVENT", "UID:a", "DTSTART:20260101T090000", "END:VEVENT")
    calendar = parse_ics(text + text.replace("UID:a", "UID:b").replace("-//t//EN", "-//u//EN"))
    assert isinstance(calendar, Calendar)
    assert len(calendar) == 2
    assert [event.uid for event in calendar] == ["a", "b"]
    assert calendar.prodids == ("-//t//EN", "-//u//EN")
    assert [event.start for event in calendar] == [datetime(2026, 1, 1, 9)] * 2


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "no VCALENDAR"),
        ("BEGIN:VEVENT\nUID:a\nEND:VEVENT\n", "line 1: expected VCALENDAR, got VEVENT"),
    ],
)
def test_ical_07_top_level_must_be_vcalendar(text: str, message: str) -> None:
    with pytest.raises(ICalParseError, match=message):
        parse_ics(text)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("BEGIN:VCALENDAR\nPRODID:x\nEND:VCALENDAR\n", "no VERSION"),
        ("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n", "no PRODID"),
        ("BEGIN:VCALENDAR\nVERSION:1.0\nPRODID:x\nEND:VCALENDAR\n", "expected 2.0"),
    ],
)
def test_ical_08_version_and_prodid_are_required(text: str, message: str) -> None:
    with pytest.raises(RuleValidationError, match=f"ICAL-08.*{message}"):
        parse_ics(text)
    with pytest.raises(ICalParseError, match="VERSION must appear only once"):
        parse_ics(_calendar("VERSION:2.0"))


def test_ical_09_unknown_components_are_ignored() -> None:
    calendar = parse_ics(
        _calendar(
            "BEGIN:X-ACME-TASK",
            "UID:x",
            "END:X-ACME-TASK",
            "BEGIN:VJOURNAL",
            "UID:j",
            "END:VJOURNAL",
        )
    )
    assert len(calendar) == 0
    assert calendar.uids == []


def test_event_errors_name_the_vevent_line() -> None:
    text = _calendar(
        "BEGIN:VEVENT",
        "UID:ok",
        "DTSTART:20260101T090000",
        "END:VEVENT",
        "BEGIN:VEVENT",
        "UID:bad",
        "DTSTART:20260101T090000",
        "RRULE:FREQ=DAILY;COUNT=2;UNTIL=20260105T090000",
        "END:VEVENT",
    )
    with pytest.raises(RuleValidationError, match="RRULE-07") as caught:
        parse_ics(text)
    assert "in VEVENT on line 8" in caught.value.__notes__
    assert "in RRULE on line 11" in caught.value.__notes__
