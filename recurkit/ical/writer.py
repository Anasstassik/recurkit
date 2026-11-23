from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime

from recurkit.expand import Occurrence
from recurkit.ical.calendar import Calendar
from recurkit.ical.event import Event, Transparency
from recurkit.ical.values import Duration, format_duration
from recurkit.recurrence_set import RecurrenceSet
from recurkit.rule.model import format_date_value
from recurkit.timezones import TimeZoneProvider

LINE_OCTETS = 75
PRODID = "-//RecurKit//RecurKit//EN"
_QUOTE_IF = frozenset(';:,"')


def fold(line: str, width: int = LINE_OCTETS) -> str:
    pieces: list[str] = []
    current: list[str] = []
    size, limit = 0, width
    for char in line:
        octets = len(char.encode("utf-8"))
        if size + octets > limit:
            pieces.append("".join(current))
            current, size, limit = [], 0, width - 1
        current.append(char)
        size += octets
    pieces.append("".join(current))
    return "\r\n ".join(pieces)


def _param_value(value: str) -> str:
    if '"' in value:
        raise ValueError(f"a parameter value cannot contain a double quote: {value!r}")
    return f'"{value}"' if _QUOTE_IF & set(value) else value


def format_content_line(name: str, value: str, params: Mapping[str, str] | None = None) -> str:
    head = name.upper() + "".join(
        f";{key.upper()}={_param_value(param)}" for key, param in (params or {}).items()
    )
    return f"{head}:{value}"


def _date_line(name: str, values: Iterable[Occurrence], params: dict[str, str]) -> str:
    text = ",".join(format_date_value(value) for value in values)
    return format_content_line(name, text, params)


def _date_lines(
    name: str,
    values: Iterable[Occurrence],
    provider: TimeZoneProvider | None,
    tzid: str | None,
) -> list[str]:
    ordered = sorted(values)
    if not ordered:
        return []
    first = ordered[0]
    if not isinstance(first, datetime):
        return [_date_line(name, ordered, {"VALUE": "DATE"})]
    if provider is None or tzid is None:
        return [_date_line(name, ordered, {})]
    local: list[datetime] = []
    utc: list[datetime] = []
    for value in ordered:
        assert isinstance(value, datetime)
        wall = provider.to_local(tzid, value)
        if provider.localize(tzid, wall) == value:
            local.append(wall)
        else:
            utc.append(value.astimezone(UTC))
    lines = [_date_line(name, local, {"TZID": tzid})] if local else []
    return lines + ([_date_line(name, utc, {})] if utc else [])


def _dtstart_line(rset: RecurrenceSet) -> str:
    start: date | datetime = rset.rule.require_dtstart()
    if not isinstance(start, datetime):
        return format_content_line("DTSTART", format_date_value(start), {"VALUE": "DATE"})
    params = {"TZID": rset.tzid} if rset.tzid is not None else {}
    return format_content_line("DTSTART", format_date_value(start), params)


def format_recurrence(rset: RecurrenceSet) -> str:
    lines = [_dtstart_line(rset), format_content_line("RRULE", rset.rule.to_text())]
    lines += _date_lines("RDATE", rset.rdates, rset.provider, rset.tzid)
    lines += _date_lines("EXDATE", rset.exdates, rset.provider, rset.tzid)
    return _join(lines)


def _join(lines: Iterable[str]) -> str:
    return "".join(fold(line) + "\r\n" for line in lines)


def escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def _moment_line(name: str, event: Event, value: Occurrence) -> str:
    if not isinstance(value, datetime):
        return format_content_line(name, format_date_value(value), {"VALUE": "DATE"})
    if event.tzid is None or event.provider is None or value.tzinfo is None:
        return format_content_line(name, format_date_value(value))
    wall = event.provider.to_local(event.tzid, value)
    if event.provider.localize(event.tzid, wall) != value:
        return format_content_line(name, format_date_value(value.astimezone(UTC)))
    return format_content_line(name, format_date_value(wall), {"TZID": event.tzid})


def format_event(event: Event) -> list[str]:
    lines = ["BEGIN:VEVENT", format_content_line("UID", event.uid)]
    if event.summary:
        lines.append(format_content_line("SUMMARY", escape_text(event.summary)))
    lines.append(_moment_line("DTSTART", event, event.start))
    if isinstance(event.length, Duration):
        if event.length != Duration() or event.all_day:
            lines.append(format_content_line("DURATION", format_duration(event.length)))
    elif event.length:
        lines.append(_moment_line("DTEND", event, event.end))
    if event.recurrence is not None:
        lines.append(format_content_line("RRULE", event.recurrence.rule.to_text()))
    lines += _date_lines("RDATE", event.rdates, event.provider, event.tzid)
    lines += _date_lines("EXDATE", event.exdates, event.provider, event.tzid)
    if event.transparency is not Transparency.OPAQUE:
        lines.append(format_content_line("TRANSP", event.transparency.value))
    if event.status is not None:
        lines.append(format_content_line("STATUS", event.status.value))
    return [*lines, "END:VEVENT"]


def format_calendar(calendar: Calendar | Iterable[Event], prodid: str = PRODID) -> str:
    if isinstance(calendar, Calendar) and calendar.prodids:
        prodid = calendar.prodids[0]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", format_content_line("PRODID", prodid)]
    for event in calendar:
        lines += format_event(event)
    return _join([*lines, "END:VCALENDAR"])
