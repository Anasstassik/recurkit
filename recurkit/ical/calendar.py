from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from recurkit.errors import ICalParseError, RecurKitError, RuleValidationError
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
    return Calendar(tuple(events), tuple(prodids))
