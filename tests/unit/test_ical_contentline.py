import pytest

from recurkit import ICalParseError
from recurkit.ical import parse_content_line, parse_content_lines, unescape_text, unfold
from recurkit.ical.contentline import split_values


def test_ical_01_unfold_joins_continuation_lines() -> None:
    text = (
        "DTSTART:20260101T090000\r\n"
        "RRULE:FREQ=WEEKLY;\r\n BYDAY=MO,\r\n\tWE\r\n"
        "\r\n"
        "EXDATE:20260105T090000"
    )
    assert list(unfold(text)) == [
        (1, "DTSTART:20260101T090000"),
        (2, "RRULE:FREQ=WEEKLY;BYDAY=MO,WE"),
        (6, "EXDATE:20260105T090000"),
    ]
    with pytest.raises(ICalParseError, match="line 1"):
        list(unfold(" orphan continuation"))


def test_ical_02_parameters_with_quoted_and_multiple_values() -> None:
    line = parse_content_line(
        'ATTENDEE;ROLE=CHAIR;DELEGATED-TO="mailto:a@x.org","mailto:b@x.org":mailto:c@x.org', 7
    )
    assert line.name == "ATTENDEE"
    assert line.params["DELEGATED-TO"] == ("mailto:a@x.org", "mailto:b@x.org")
    assert line.param("role") == "CHAIR"
    assert line.value == "mailto:c@x.org"
    assert line.line == 7
    zoned = parse_content_line('dtstart;tzid="America/New_York":19970902T090000')
    assert (zoned.name, zoned.param("TZID"), zoned.value) == (
        "DTSTART",
        "America/New_York",
        "19970902T090000",
    )
    assert zoned.param("VALUE") is None
    with pytest.raises(ICalParseError, match="one value"):
        line.param("DELEGATED-TO")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("DTSTART20260101", "expected ':'"),
        (";X=1:v", "expected a name"),
        ('X;P="unterminated:v', "expected '\"'"),
        ("X;P=1;P=2:v", "repeated"),
        ("X;P:v", "expected '='"),
    ],
)
def test_malformed_lines_report_line_numbers(text: str, message: str) -> None:
    with pytest.raises(ICalParseError, match=message) as info:
        parse_content_lines("SUMMARY:ok\n" + text)
    assert info.value.line == 2


def test_ical_03_text_values_are_unescaped_and_lists_split() -> None:
    assert unescape_text(r"Meeting\, room 1\; floor 2\nbring \\laptop") == (
        "Meeting, room 1; floor 2\nbring \\laptop"
    )
    with pytest.raises(ICalParseError, match="escape"):
        unescape_text(r"bad \x")
    assert split_values("20260101T090000, 20260102T090000,") == [
        "20260101T090000",
        "20260102T090000",
    ]
