from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime

from recurkit.errors import ICalParseError, RecurKitError, RuleValidationError
from recurkit.expand import Occurrence
from recurkit.ical.components import Component, parse_components
from recurkit.ical.event import Event, parse_event
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider

SUPPORTED_VERSION = "2.0"


@dataclass(frozen=True)
class Calendar:
    events: tuple[Event, ...] = ()
    prodids: tuple[str, ...] = ()

    def __iter__(self) -> Iterator[Event]:
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)

    def by_uid(self, uid: str) -> list[Event]:
        return [event for event in self.events if event.uid == uid]

    @property
    def uids(self) -> list[str]:
        return list(dict.fromkeys(event.uid for event in self.events))


def _check_header(calendar: Component) -> str:
    version = calendar.first("VERSION")
    prodid = calendar.first("PRODID")
    if version is None or prodid is None:
        missing = "VERSION" if version is None else "PRODID"
        raise RuleValidationError("ICAL-08", f"VCALENDAR on line {calendar.line} has no {missing}")
    if version.value.strip() != SUPPORTED_VERSION:
        raise RuleValidationError(
            "ICAL-08", f"VERSION on line {version.line} is {version.value!r}, expected 2.0"
        )
    return prodid.value


def _event(component: Component, provider: TimeZoneProvider) -> Event:
    try:
        return parse_event(component, provider=provider)
    except RecurKitError as exc:
        exc.add_note(f"in VEVENT on line {component.line}")
        raise


def _kind(value: Occurrence) -> str:
    if not isinstance(value, datetime):
        return "DATE"
    return "floating DATE-TIME" if value.tzinfo is None else "UTC or zoned DATE-TIME"


def _with_overrides(master: Event, overrides: list[Event]) -> Event:
    seen: set[Occurrence] = set()
    for override in overrides:
        assert override.recurrence_id is not None
        if _kind(override.recurrence_id) != _kind(master.start):
            raise RuleValidationError(
                "RID-01",
                f"RECURRENCE-ID of the VEVENT on line {override.line} must be a "
                f"{_kind(master.start)} like DTSTART of {master.uid}",
            )
        if override.recurrence_id in seen:
            raise ICalParseError(
                f"{master.uid} has two overrides for {override.recurrence_id}", line=override.line
            )
        seen.add(override.recurrence_id)
    ordered = sorted(overrides, key=lambda event: event.line)
    return replace(master, overrides=tuple(ordered))


def attach_overrides(events: list[Event]) -> list[Event]:
    masters: dict[str, Event] = {}
    pending: dict[str, list[Event]] = {}
    for event in events:
        if not event.is_override:
            if event.uid in masters:
                raise ICalParseError(f"two VEVENTs share UID {event.uid}", line=event.line)
            masters[event.uid] = event
        else:
            pending.setdefault(event.uid, []).append(event)
    result: list[Event] = []
    for event in events:
        if not event.is_override:
            result.append(_with_overrides(event, pending.get(event.uid, [])))
        elif event.uid not in masters:
            result.append(event)
    return result


def parse_ics(text: str, *, provider: TimeZoneProvider | None = None) -> Calendar:
    zones = provider if provider is not None else ZoneInfoProvider()
    roots = parse_components(text)
    if not roots:
        raise ICalParseError("the text contains no VCALENDAR")
    events: list[Event] = []
    prodids: list[str] = []
    for root in roots:
        if root.name != "VCALENDAR":
            raise ICalParseError(f"expected VCALENDAR, got {root.name}", line=root.line)
        prodids.append(_check_header(root))
        events.extend(_event(child, zones) for child in root.components("VEVENT"))
    return Calendar(tuple(attach_overrides(events)), tuple(prodids))
