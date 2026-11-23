import pytest

from recurkit import ICalParseError
from recurkit.ical import Component, parse_components

CALENDAR = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//RecurKit//Tests//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:a@example.com\r\n"
    "DTSTART:20260105T090000\r\n"
    "BEGIN:VALARM\r\n"
    "ACTION:DISPLAY\r\n"
    "END:VALARM\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:b@example.com\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_ical_04_components_nest_with_line_numbers() -> None:
    (calendar,) = parse_components(CALENDAR)
    assert calendar.name == "VCALENDAR"
    assert calendar.line == 1
    assert [prop.name for prop in calendar.properties] == ["VERSION", "PRODID"]
    first, second = calendar.components("VEVENT")
    assert (first.line, second.line) == (4, 11)
    assert first.required("UID").value == "a@example.com"
    assert [child.name for child in first.children] == ["VALARM"]
    assert [component.name for component in calendar.walk()] == [
        "VCALENDAR",
        "VEVENT",
        "VALARM",
        "VEVENT",
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VCALENDAR\n",
            "line 3: END:VCALENDAR closes BEGIN:VEVENT",
        ),
        ("END:VEVENT\n", "line 1: END:VEVENT without BEGIN"),
        (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VEVENT\n",
            "line 1: BEGIN:VCALENDAR is never closed",
        ),
        ("BEGIN:\nEND:\n", "line 1: BEGIN needs a plain component name"),
        ("BEGIN;X=1:VEVENT\nEND:VEVENT\n", "needs a plain component name"),
    ],
)
def test_ical_04_unbalanced_components_are_rejected(text: str, message: str) -> None:
    with pytest.raises(ICalParseError, match=message):
        parse_components(text)


def test_ical_05_properties_outside_components_are_rejected() -> None:
    with pytest.raises(ICalParseError, match="line 4: SUMMARY is outside of any component"):
        parse_components("BEGIN:VCALENDAR\nEND:VCALENDAR\n\nSUMMARY:stray\n")


def test_ical_06_names_are_case_insensitive() -> None:
    (calendar,) = parse_components(
        "begin:vcalendar\nversion:2.0\nBegin:VEvent\nuid:x\nend:VEVENT\nEnd:VCalendar\n"
    )
    assert calendar.name == "VCALENDAR"
    assert calendar.first("Version") is not None
    (event,) = calendar.components("vevent")
    assert event.required("UID").value == "x"


def test_component_property_lookup_rules() -> None:
    (event,) = parse_components(
        "BEGIN:VEVENT\nUID:1\nUID:2\nRDATE:20260101\nRDATE:20260102\nEND:VEVENT\n"
    )
    assert [prop.value for prop in event.all("RDATE")] == ["20260101", "20260102"]
    assert event.first("SUMMARY") is None
    with pytest.raises(ICalParseError, match="line 3: UID must appear only once in VEVENT"):
        event.first("UID")
    with pytest.raises(ICalParseError, match="line 1: VEVENT has no DTSTART"):
        event.required("DTSTART")


def test_several_top_level_calendars() -> None:
    roots = parse_components("BEGIN:VCALENDAR\nEND:VCALENDAR\nBEGIN:VCALENDAR\nEND:VCALENDAR\n")
    assert [root.line for root in roots] == [1, 3]
    assert roots[0] == Component("VCALENDAR", 1)
