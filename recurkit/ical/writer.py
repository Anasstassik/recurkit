from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime

from recurkit.expand import Occurrence
from recurkit.recurrence_set import RecurrenceSet
from recurkit.rule.model import format_date_value

LINE_OCTETS = 75
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


def _date_lines(rset: RecurrenceSet, name: str, values: Iterable[Occurrence]) -> list[str]:
    ordered = sorted(values)
    if not ordered:
        return []
    first = ordered[0]
    if not isinstance(first, datetime):
        return [_date_line(name, ordered, {"VALUE": "DATE"})]
    if rset.provider is None or rset.tzid is None:
        return [_date_line(name, ordered, {})]
    provider, tzid = rset.provider, rset.tzid
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
    lines += _date_lines(rset, "RDATE", rset.rdates)
    lines += _date_lines(rset, "EXDATE", rset.exdates)
    return "".join(fold(line) + "\r\n" for line in lines)
