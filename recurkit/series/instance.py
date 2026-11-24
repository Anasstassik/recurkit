from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from recurkit.expand import Occurrence
from recurkit.ical import Event, EventStatus, Transparency


def sort_key(value: Occurrence) -> datetime:
    if not isinstance(value, datetime):
        return datetime.combine(value, time.min)
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def same_kind(value: Occurrence, reference: Occurrence) -> bool:
    if not isinstance(reference, datetime):
        return isinstance(value, date) and not isinstance(value, datetime)
    if not isinstance(value, datetime):
        return False
    return (value.tzinfo is None) == (reference.tzinfo is None)


@dataclass(frozen=True)
class Instance:
    uid: str
    recurrence_id: Occurrence
    start: Occurrence
    end: Occurrence
    summary: str = ""
    status: EventStatus | None = None
    transparency: Transparency = Transparency.OPAQUE
    overridden: bool = False

    @property
    def cancelled(self) -> bool:
        return self.status is EventStatus.CANCELLED

    @property
    def moved(self) -> bool:
        return self.start != self.recurrence_id

    @property
    def busy(self) -> bool:
        return not self.cancelled and self.transparency is Transparency.OPAQUE

    @property
    def key(self) -> tuple[datetime, datetime]:
        return sort_key(self.start), sort_key(self.recurrence_id)

    @classmethod
    def of_master(cls, master: Event, start: Occurrence) -> Instance:
        return cls(
            uid=master.uid,
            recurrence_id=start,
            start=start,
            end=master.end_for(start),
            summary=master.summary,
            status=master.status,
            transparency=master.transparency,
        )

    @classmethod
    def of_override(cls, override: Event) -> Instance:
        if override.recurrence_id is None:
            raise ValueError(f"the VEVENT on line {override.line} has no RECURRENCE-ID")
        return cls(
            uid=override.uid,
            recurrence_id=override.recurrence_id,
            start=override.start,
            end=override.end,
            summary=override.summary,
            status=override.status,
            transparency=override.transparency,
            overridden=True,
        )
