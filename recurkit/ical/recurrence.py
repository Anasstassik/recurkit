"""Build a RecurrenceSet from the recurrence properties of an event.

Input is the text RFC 5545 uses in its examples::

    DTSTART;TZID=America/New_York:19970902T090000
    RRULE:FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13
    EXDATE;TZID=America/New_York:19970902T090000

DTSTART comes in three forms (DT-01): floating, UTC (``Z``) and local with
a TZID; ``VALUE=DATE`` makes an all-day series. Other properties are ignored,
so the lines of a whole VEVENT can be passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from recurkit.errors import ICalParseError, RecurKitError, RuleValidationError
from recurkit.expand import Occurrence
from recurkit.ical.contentline import ContentLine, parse_content_lines, split_values
from recurkit.recurrence_set import RecurrenceSet
from recurkit.rule import Rule, parse_date_or_datetime
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider


@dataclass(frozen=True)
class DateValue:
    """A DATE or DATE-TIME property value with the zone it is written in."""

    value: date | datetime
    tzid: str | None = None

    @property
    def is_date(self) -> bool:
        return not isinstance(self.value, datetime)


def parse_date_value(text: str, line: ContentLine) -> DateValue:
    """Interpret one DATE / DATE-TIME value of ``line`` with its VALUE and TZID parameters."""
    kind = (line.param("VALUE") or "DATE-TIME").upper()
    if kind == "PERIOD":
        raise ICalParseError(f"{line.name} values of type PERIOD are not supported", line=line.line)
    if kind not in ("DATE", "DATE-TIME"):
        raise ICalParseError(f"{line.name} cannot have VALUE={kind}", line=line.line)
    try:
        value = parse_date_or_datetime(text)
    except RuleValidationError:
        raise
    except ValueError as exc:
        raise ICalParseError(f"{line.name}: {exc}", line=line.line) from None
    if (kind == "DATE") != (not isinstance(value, datetime)):
        raise ICalParseError(f"{line.name}: {text!r} is not a {kind} value", line=line.line)
    tzid = line.param("TZID")
    if tzid is not None:
        if not isinstance(value, datetime):
            raise RuleValidationError("DT-04", f"{line.name}: TZID must not be applied to a DATE")
        if value.tzinfo is not None:
            raise RuleValidationError("DT-02", f"{line.name}: TZID must not be applied to UTC")
    return DateValue(value, tzid)


def _single(lines: list[ContentLine], name: str) -> ContentLine | None:
    found = [line for line in lines if line.name == name]
    if len(found) > 1:
        raise ICalParseError(f"{name} must appear only once", line=found[1].line)
    return found[0] if found else None


class _Collector:
    """Turns RDATE/EXDATE values into values comparable with the set's DTSTART."""

    def __init__(self, dtstart: DateValue, provider: TimeZoneProvider):
        self.dtstart = dtstart
        self.provider = provider

    def convert(self, item: DateValue, line: ContentLine) -> Occurrence:
        if item.is_date != self.dtstart.is_date:
            raise ICalParseError(
                f"{line.name} must have the same value type as DTSTART", line=line.line
            )
        value, start = item.value, self.dtstart.value
        if not isinstance(value, datetime) or not isinstance(start, datetime):
            return value
        if item.tzid is not None and item.tzid != self.dtstart.tzid:
            return self.provider.localize(item.tzid, value)  # another zone: an instant
        if self.dtstart.tzid is None and (value.tzinfo is None) != (start.tzinfo is None):
            raise ICalParseError(
                f"{line.name}: cannot mix floating and UTC values with DTSTART", line=line.line
            )
        return value

    def values(self, lines: list[ContentLine], name: str) -> list[Occurrence]:
        result = []
        for line in lines:
            if line.name == name:
                for text in split_values(line.value):
                    result.append(self.convert(parse_date_value(text, line), line))
        return result


def parse_recurrence(text: str, *, provider: TimeZoneProvider | None = None) -> RecurrenceSet:
    """Build the recurrence set described by DTSTART, RRULE, RDATE and EXDATE lines.

    Raises :class:`ICalParseError` (with a line number) for malformed text and
    the rule errors of :meth:`Rule.parse` for an invalid RRULE.
    """
    lines = parse_content_lines(text)
    start_line = _single(lines, "DTSTART")
    if start_line is None:
        raise ICalParseError("DTSTART is required")
    dtstart = parse_date_value(start_line.value, start_line)
    rule_line = _single(lines, "RRULE")
    if rule_line is None:
        raise ICalParseError("RRULE is required")
    zones = provider if provider is not None else ZoneInfoProvider()
    try:
        rule = Rule.parse(rule_line.value, dtstart=dtstart.value, tzid=dtstart.tzid)
    except RecurKitError as exc:
        exc.add_note(f"in RRULE on line {rule_line.line}")
        raise
    collector = _Collector(dtstart, zones)
    return RecurrenceSet(
        rule,
        rdates=collector.values(lines, "RDATE"),
        exdates=collector.values(lines, "EXDATE"),
        provider=zones if dtstart.tzid else None,
    )
