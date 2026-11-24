from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum

from recurkit.errors import ICalParseError, RuleValidationError
from recurkit.expand import Occurrence
from recurkit.ical.components import Component
from recurkit.ical.contentline import ContentLine, unescape_text
from recurkit.ical.recurrence import DateCollector, DateValue, build_recurrence, parse_date_value
from recurkit.ical.values import Duration, parse_duration
from recurkit.recurrence_set import RecurrenceSet, merge_unique, unique_sorted
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider

_ONE_DAY = Duration(days=1)
_NO_TIME = Duration()


class Transparency(Enum):
    OPAQUE = "OPAQUE"
    TRANSPARENT = "TRANSPARENT"


class EventStatus(Enum):
    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Event:
    uid: str
    start: Occurrence
    length: timedelta | Duration
    summary: str = ""
    transparency: Transparency = Transparency.OPAQUE
    status: EventStatus | None = None
    recurrence: RecurrenceSet | None = field(default=None, compare=False)
    rdates: tuple[Occurrence, ...] = ()
    exdates: frozenset[Occurrence] = frozenset()
    tzid: str | None = None
    provider: TimeZoneProvider | None = field(default=None, compare=False, repr=False)
    line: int = 0

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, datetime)

    @property
    def end(self) -> Occurrence:
        return self.end_for(self.start)

    @property
    def cancelled(self) -> bool:
        return self.status is EventStatus.CANCELLED

    def _zone(self, instant: datetime) -> datetime:
        if self.tzid is None or self.provider is None:
            return instant
        utc = instant.astimezone(UTC)
        return utc.astimezone(timezone(self.provider.utc_offset(self.tzid, utc), self.tzid))

    def end_for(self, start: Occurrence) -> Occurrence:
        if not isinstance(start, datetime):
            if isinstance(self.length, Duration):
                return self.length.add_to_local(start)
            return start + timedelta(days=self.length.days)
        if isinstance(self.length, timedelta):
            exact = self.length
        else:
            exact = self.length.exact
            if self.length.nominal_days:
                start = self._shift_days(start, self.length.nominal_days)
        if start.tzinfo is None:
            return start + exact
        return self._zone(start.astimezone(UTC) + exact)

    def _shift_days(self, start: datetime, days: int) -> datetime:
        if start.tzinfo is None or self.tzid is None or self.provider is None:
            return start + timedelta(days=days)
        local = self.provider.to_local(self.tzid, start) + timedelta(days=days)
        return self.provider.localize(self.tzid, local)

    def starts_between(self, low: Occurrence, high: Occurrence) -> Iterator[Occurrence]:
        if high < low:
            raise ValueError("the end of the window is before its start")
        values = self.recurrence.between(low, high) if self.recurrence else self.starts()
        for value in values:
            if value >= high:
                return
            if value >= low:
                yield value

    def starts(self) -> Iterator[Occurrence]:
        if self.recurrence is not None:
            yield from self.recurrence.occurrences()
            return
        for value in merge_unique([self.start], self.rdates):
            if value not in self.exdates:
                yield value


def _place(value: Occurrence, dtstart: DateValue, provider: TimeZoneProvider) -> Occurrence:
    if dtstart.tzid is None or not isinstance(value, datetime) or value.tzinfo is not None:
        return value
    return provider.localize(dtstart.tzid, value)


def _check_end(end: DateValue, dtstart: DateValue, line: ContentLine) -> None:
    if end.is_date != dtstart.is_date:
        raise RuleValidationError("EVT-04", "DTEND must have the same value type as DTSTART")
    floating = [
        isinstance(item.value, datetime) and item.value.tzinfo is None and item.tzid is None
        for item in (end, dtstart)
    ]
    if floating[0] != floating[1]:
        raise RuleValidationError(
            "EVT-04", f"DTEND on line {line.line} must be floating exactly when DTSTART is"
        )


def _length(
    component: Component, dtstart: DateValue, start: Occurrence, provider: TimeZoneProvider
) -> timedelta | Duration:
    end_line, duration_line = component.first("DTEND"), component.first("DURATION")
    if end_line is not None and duration_line is not None:
        raise RuleValidationError("EVT-02", "DTEND and DURATION must not both be present")
    if end_line is not None:
        end_value = parse_date_value(end_line.value, end_line)
        _check_end(end_value, dtstart, end_line)
        length = _place(end_value.value, end_value, provider) - start
        if length <= timedelta(0):
            raise RuleValidationError(
                "EVT-03", f"DTEND on line {end_line.line} is not after DTSTART"
            )
        return length
    if duration_line is not None:
        duration = parse_duration(duration_line.value, duration_line.line)
        if dtstart.is_date and not duration.is_whole_days:
            raise RuleValidationError(
                "EVT-06", "an all-day event needs a DURATION in days or weeks"
            )
        if duration.negative:
            raise RuleValidationError("EVT-03", "DURATION must not be negative")
        return duration
    return _ONE_DAY if dtstart.is_date else _NO_TIME


def _enum[E: Enum](component: Component, name: str, kind: type[E]) -> E | None:
    line = component.first(name)
    if line is None:
        return None
    try:
        return kind(line.value.strip().upper())
    except ValueError:
        raise RuleValidationError(
            "EVT-07", f"{name} on line {line.line} cannot be {line.value!r}"
        ) from None


def parse_event(component: Component, *, provider: TimeZoneProvider | None = None) -> Event:
    if component.name != "VEVENT":
        raise ICalParseError(f"expected VEVENT, got {component.name}", line=component.line)
    zones = provider if provider is not None else ZoneInfoProvider()
    uid = component.first("UID")
    start_line = component.first("DTSTART")
    if uid is None or start_line is None:
        missing = "UID" if uid is None else "DTSTART"
        raise RuleValidationError("EVT-01", f"VEVENT on line {component.line} has no {missing}")
    dtstart = parse_date_value(start_line.value, start_line)
    if dtstart.tzid is not None:
        zones.check_zone(dtstart.tzid)
    start = _place(dtstart.value, dtstart, zones)
    collector = DateCollector(dtstart, zones)
    rdates = collector.values(component.properties, "RDATE")
    exdates = collector.values(component.properties, "EXDATE")
    summary = component.first("SUMMARY")
    return Event(
        uid=uid.value,
        start=start,
        length=_length(component, dtstart, start, zones),
        summary=unescape_text(summary.value) if summary is not None else "",
        transparency=_enum(component, "TRANSP", Transparency) or Transparency.OPAQUE,
        status=_enum(component, "STATUS", EventStatus),
        recurrence=build_recurrence(component.properties, dtstart, zones),
        rdates=tuple(unique_sorted(_place(v, dtstart, zones) for v in rdates)),
        exdates=frozenset(_place(v, dtstart, zones) for v in exdates),
        tzid=dtstart.tzid,
        provider=zones if dtstart.tzid else None,
        line=component.line,
    )
