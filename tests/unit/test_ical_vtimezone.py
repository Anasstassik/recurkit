from datetime import datetime, timedelta
from itertools import islice

import pytest

from recurkit import ICalParseError, RuleValidationError, parse_ics
from recurkit.expand import occurrences
from recurkit.ical import (
    ObservanceKind,
    VTimezone,
    parse_components,
    parse_utc_offset,
    parse_vtimezone,
)

HEADER = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\n"
NEW_YORK = """BEGIN:VTIMEZONE
TZID:America/New_York
LAST-MODIFIED:20050809T050000Z
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
END:DAYLIGHT
END:VTIMEZONE
"""
NEW_YORK_1967 = """BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
DTSTART:19670430T020000
RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=-1SU;UNTIL=19730429T070000Z
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19671029T020000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU;UNTIL=20061029T060000Z
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19740106T020000
RDATE:19750223T020000
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
END:DAYLIGHT
END:VTIMEZONE
"""


def _zone(text: str) -> VTimezone:
    (component,) = parse_components(text)
    return parse_vtimezone(component)


def test_tzc_03_rfc_example_with_rules_gives_both_observances() -> None:
    zone = _zone(NEW_YORK)
    assert zone.tzid == "America/New_York"
    daylight, standard = zone.observances
    assert (daylight.kind, daylight.name) == (ObservanceKind.DAYLIGHT, "EDT")
    assert (daylight.offset_from, daylight.offset_to) == (timedelta(hours=-5), timedelta(hours=-4))
    assert (standard.kind, standard.name) == (ObservanceKind.STANDARD, "EST")
    assert standard.rule is not None and daylight.rule is not None
    assert list(islice(occurrences(daylight.rule), 3)) == [
        datetime(2007, 3, 11, 2),
        datetime(2008, 3, 9, 2),
        datetime(2009, 3, 8, 2),
    ]
    assert list(islice(occurrences(standard.rule), 2)) == [
        datetime(2007, 11, 4, 2),
        datetime(2008, 11, 2, 2),
    ]


def test_tzc_05_utc_until_becomes_the_local_time_before_the_change() -> None:
    first, standard, last = _zone(NEW_YORK_1967).observances
    assert first.rule is not None and standard.rule is not None
    assert first.rule.until == datetime(1973, 4, 29, 2)
    assert list(occurrences(first.rule))[-1] == datetime(1973, 4, 29, 2)
    assert standard.rule.until == datetime(2006, 10, 29, 2)
    assert list(occurrences(standard.rule))[-1] == datetime(2006, 10, 29, 2)
    assert (last.start, last.rule, last.rdates) == (
        datetime(1974, 1, 6, 2),
        None,
        (datetime(1975, 2, 23, 2),),
    )


@pytest.mark.parametrize(
    ("text", "offset"),
    [
        ("-0500", timedelta(hours=-5)),
        ("+0530", timedelta(hours=5, minutes=30)),
        ("+0000", timedelta(0)),
        ("+124500", timedelta(hours=12, minutes=45)),
        ("-001914", -timedelta(minutes=19, seconds=14)),
    ],
)
def test_tzc_04_utc_offsets_are_read(text: str, offset: timedelta) -> None:
    assert parse_utc_offset(text) == offset


@pytest.mark.parametrize("text", ["-0000", "-000000", "0500", "+5", "+0560", "+050060", "+05:00"])
def test_tzc_04_malformed_utc_offsets_are_rejected(text: str) -> None:
    with pytest.raises(RuleValidationError) as caught:
        parse_utc_offset(text)
    assert caught.value.requirement_id == "TZC-04"


@pytest.mark.parametrize(
    ("old", "new", "requirement"),
    [
        ("TZID:America/New_York\n", "TZID: \n", "TZC-01"),
        ("TZOFFSETFROM:-0500\n", "", "TZC-03"),
        ("TZOFFSETTO:-0400\n", "", "TZC-03"),
        ("DTSTART:20070311T020000", "DTSTART:20070311T070000Z", "TZC-03"),
        ("DTSTART:20070311T020000", "DTSTART;VALUE=DATE:20070311", "TZC-03"),
        ("TZOFFSETTO:-0400", "TZOFFSETTO:-0000", "TZC-04"),
    ],
)
def test_tzc_01_to_04_broken_observances_name_the_requirement(
    old: str, new: str, requirement: str
) -> None:
    with pytest.raises(RuleValidationError) as caught:
        _zone(NEW_YORK.replace(old, new, 1))
    assert caught.value.requirement_id == requirement
    if requirement != "TZC-01":
        assert "in VTIMEZONE America/New_York on line 1" in caught.value.__notes__


def test_tzc_02_vtimezone_needs_an_observance() -> None:
    with pytest.raises(RuleValidationError, match="TZC-02"):
        _zone("BEGIN:VTIMEZONE\nTZID:Empty\nEND:VTIMEZONE\n")
    with pytest.raises(ICalParseError, match="no TZID"):
        _zone(NEW_YORK.replace("TZID:America/New_York\n", ""))


def test_tzc_01_calendar_keeps_zones_by_unique_tzid() -> None:
    calendar = parse_ics(HEADER + NEW_YORK + "END:VCALENDAR\n")
    zone = calendar.timezone("America/New_York")
    assert zone is not None and len(zone.observances) == 2
    assert calendar.timezone("Europe/Kyiv") is None
    with pytest.raises(ICalParseError, match="share TZID America/New_York"):
        parse_ics(HEADER + NEW_YORK + NEW_YORK + "END:VCALENDAR\n")
