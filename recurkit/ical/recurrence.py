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
    value: date | datetime
    tzid: str | None = None

    @property
    def is_date(self) -> bool:
        return not isinstance(self.value, datetime)


def parse_date_value(text: str, line: ContentLine) -> DateValue:
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


class DateCollector:
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
            return self.provider.localize(item.tzid, value)
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


def build_recurrence(
    lines: list[ContentLine], dtstart: DateValue, provider: TimeZoneProvider
) -> RecurrenceSet | None:
    rule_line = _single(lines, "RRULE")
    if rule_line is None:
        return None
    try:
        rule = Rule.parse(rule_line.value, dtstart=dtstart.value, tzid=dtstart.tzid)
    except RecurKitError as exc:
        exc.add_note(f"in RRULE on line {rule_line.line}")
        raise
    collector = DateCollector(dtstart, provider)
    return RecurrenceSet(
        rule,
        rdates=collector.values(lines, "RDATE"),
        exdates=collector.values(lines, "EXDATE"),
        provider=provider if dtstart.tzid else None,
    )


def parse_recurrence(text: str, *, provider: TimeZoneProvider | None = None) -> RecurrenceSet:
    lines = parse_content_lines(text)
    start_line = _single(lines, "DTSTART")
    if start_line is None:
        raise ICalParseError("DTSTART is required")
    dtstart = parse_date_value(start_line.value, start_line)
    zones = provider if provider is not None else ZoneInfoProvider()
    recurrence = build_recurrence(lines, dtstart, zones)
    if recurrence is None:
        raise ICalParseError("RRULE is required")
    return recurrence
