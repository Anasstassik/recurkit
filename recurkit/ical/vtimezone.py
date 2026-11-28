from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

from recurkit.errors import ICalParseError, RecurKitError, RuleValidationError
from recurkit.ical.components import Component
from recurkit.ical.contentline import ContentLine, split_values
from recurkit.ical.recurrence import parse_date_value
from recurkit.rule import Rule, parse_rrule, validate

_UTC_OFFSET = re.compile(r"([+-])(\d\d)(\d\d)(\d\d)?", re.ASCII)


class ObservanceKind(Enum):
    STANDARD = "STANDARD"
    DAYLIGHT = "DAYLIGHT"


@dataclass(frozen=True)
class Observance:
    kind: ObservanceKind
    start: datetime
    offset_from: timedelta
    offset_to: timedelta
    rule: Rule | None = None
    rdates: tuple[datetime, ...] = ()
    name: str | None = None
    line: int = 0


@dataclass(frozen=True)
class VTimezone:
    tzid: str
    observances: tuple[Observance, ...]
    line: int = 0


def parse_utc_offset(text: str, line: int | None = None) -> timedelta:
    match = _UTC_OFFSET.fullmatch(text.strip())
    if match is None:
        raise RuleValidationError("TZC-04", f"line {line}: {text!r} is not a UTC-OFFSET value")
    sign, hours, minutes, seconds = match.groups()
    if int(minutes) > 59 or int(seconds or 0) > 59:
        raise RuleValidationError("TZC-04", f"line {line}: {text!r} has minutes or seconds over 59")
    if sign == "-" and not int(hours + minutes + (seconds or "0")):
        raise RuleValidationError("TZC-04", f"line {line}: {text!r} must be written as +0000")
    size = timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds or 0))
    return -size if sign == "-" else size


def _local(line: ContentLine, text: str) -> datetime:
    value = parse_date_value(text, line)
    if not isinstance(value.value, datetime) or value.value.tzinfo or value.tzid:
        raise RuleValidationError(
            "TZC-03", f"{line.name} on line {line.line} must be a local DATE-TIME"
        )
    return value.value


def _rule(line: ContentLine, start: datetime, offset_from: timedelta) -> Rule:
    parts = parse_rrule(line.value, dtstart=start)
    until = parts.until
    if isinstance(until, datetime) and until.tzinfo is not None:
        parts = replace(parts, until=(until + offset_from).replace(tzinfo=None))
    return validate(parts)


def _offset(component: Component, name: str) -> timedelta:
    found = component.first(name)
    if found is None:
        raise RuleValidationError(
            "TZC-03", f"{component.name} on line {component.line} has no {name}"
        )
    return parse_utc_offset(found.value, found.line)


def _observance(component: Component) -> Observance:
    dtstart = component.required("DTSTART")
    start = _local(dtstart, dtstart.value)
    offset_from = _offset(component, "TZOFFSETFROM")
    offset_to = _offset(component, "TZOFFSETTO")
    rrule = component.first("RRULE")
    name = component.all("TZNAME")
    return Observance(
        kind=ObservanceKind(component.name),
        start=start,
        offset_from=offset_from,
        offset_to=offset_to,
        rule=None if rrule is None else _rule(rrule, start, offset_from),
        rdates=tuple(
            sorted(
                _local(rd, text) for rd in component.all("RDATE") for text in split_values(rd.value)
            )
        ),
        name=name[0].value if name else None,
        line=component.line,
    )


def parse_vtimezone(component: Component) -> VTimezone:
    tzid = component.required("TZID").value.strip()
    if not tzid:
        raise RuleValidationError("TZC-01", f"VTIMEZONE on line {component.line} has an empty TZID")
    observances = [c for c in component.children if c.name in ("STANDARD", "DAYLIGHT")]
    if not observances:
        raise RuleValidationError(
            "TZC-02", f"VTIMEZONE {tzid} on line {component.line} has no STANDARD or DAYLIGHT"
        )
    try:
        parsed = tuple(_observance(child) for child in observances)
    except RecurKitError as exc:
        exc.add_note(f"in VTIMEZONE {tzid} on line {component.line}")
        raise
    return VTimezone(tzid, tuple(sorted(parsed, key=lambda o: o.start)), component.line)


def parse_vtimezones(calendar: Component) -> tuple[VTimezone, ...]:
    zones: dict[str, VTimezone] = {}
    for child in calendar.components("VTIMEZONE"):
        zone = parse_vtimezone(child)
        if zone.tzid in zones:
            raise ICalParseError(f"two VTIMEZONEs share TZID {zone.tzid}", line=zone.line)
        zones[zone.tzid] = zone
    return tuple(zones.values())
