from __future__ import annotations

import heapq
from collections.abc import Iterable, Iterator
from dataclasses import replace

from recurkit.errors import SeriesError
from recurkit.expand import Occurrence
from recurkit.ical import Event, EventStatus, Transparency
from recurkit.series.instance import Instance, same_kind, sort_key


class Series:
    def __init__(self, master: Event, overrides: Iterable[Event] = ()):
        if master.is_override:
            raise SeriesError(f"the VEVENT on line {master.line} is an override, not a master")
        self.master = replace(master, overrides=())
        self._overrides: dict[Occurrence, Instance] = {}
        for override in overrides:
            self._add(Instance.of_override(override))

    @classmethod
    def from_event(cls, event: Event) -> Series:
        return cls(event, event.overrides)

    @property
    def uid(self) -> str:
        return self.master.uid

    @property
    def overrides(self) -> list[Instance]:
        return sorted(self._overrides.values(), key=lambda item: item.key)

    def _add(self, instance: Instance) -> None:
        if instance.uid != self.uid:
            raise SeriesError(f"an override of {instance.uid} cannot change {self.uid}")
        for value, name in ((instance.recurrence_id, "RECURRENCE-ID"), (instance.start, "start")):
            if not same_kind(value, self.master.start):
                raise SeriesError(f"{name} {value!r} is not the same kind of value as DTSTART")
        self._overrides[instance.recurrence_id] = instance

    def is_instance(self, recurrence_id: Occurrence) -> bool:
        if not same_kind(recurrence_id, self.master.start):
            return False
        if self.master.recurrence is not None:
            return self.master.recurrence.after(recurrence_id, inclusive=True) == recurrence_id
        return recurrence_id in set(self.master.starts())

    def instance(self, recurrence_id: Occurrence) -> Instance | None:
        found = self._overrides.get(recurrence_id)
        if found is not None:
            return found
        if self.is_instance(recurrence_id):
            return Instance.of_master(self.master, recurrence_id)
        return None

    def _merged(self, starts: Iterable[Occurrence], extra: list[Instance]) -> Iterator[Instance]:
        plain = (
            Instance.of_master(self.master, start)
            for start in starts
            if start not in self._overrides
        )
        ordered = sorted(extra, key=lambda item: item.key)
        return heapq.merge(plain, ordered, key=lambda item: item.key)

    def instances(self, *, include_cancelled: bool = False) -> Iterator[Instance]:
        for item in self._merged(self.master.starts(), list(self._overrides.values())):
            if include_cancelled or not item.cancelled:
                yield item

    def between(
        self, low: Occurrence, high: Occurrence, *, include_cancelled: bool = False
    ) -> Iterator[Instance]:
        window = sort_key(low), sort_key(high)
        moved = [
            item
            for item in self._overrides.values()
            if window[0] <= sort_key(item.start) < window[1]
        ]
        for item in self._merged(self.master.starts_between(low, high), moved):
            if include_cancelled or not item.cancelled:
                yield item

    def _existing(self, recurrence_id: Occurrence) -> Instance:
        current = self.instance(recurrence_id)
        if current is None:
            raise SeriesError(f"{recurrence_id!r} is not an instance of {self.uid}", uid=self.uid)
        return current

    def override(
        self,
        recurrence_id: Occurrence,
        *,
        start: Occurrence | None = None,
        end: Occurrence | None = None,
        summary: str | None = None,
        status: EventStatus | None = None,
        transparency: Transparency | None = None,
    ) -> Instance:
        current = self._existing(recurrence_id)
        new_start = current.start if start is None else start
        if not same_kind(new_start, self.master.start):
            raise SeriesError(
                f"start {new_start!r} is not the same kind of value as DTSTART", uid=self.uid
            )
        if end is None:
            end = new_start + (sort_key(current.end) - sort_key(current.start))
        if not same_kind(end, self.master.start):
            raise SeriesError(f"end {end!r} is not the same kind of value as DTSTART", uid=self.uid)
        if sort_key(end) < sort_key(new_start):
            raise SeriesError(f"end {end!r} is before start {new_start!r}", uid=self.uid)
        changed = replace(
            current,
            start=new_start,
            end=end,
            summary=current.summary if summary is None else summary,
            status=current.status if status is None else status,
            transparency=current.transparency if transparency is None else transparency,
            overridden=True,
        )
        self._add(changed)
        return changed

    def cancel(self, recurrence_id: Occurrence) -> Instance:
        return self.override(recurrence_id, status=EventStatus.CANCELLED)

    def restore(self, recurrence_id: Occurrence) -> Instance | None:
        self._existing(recurrence_id)
        self._overrides.pop(recurrence_id, None)
        return self.instance(recurrence_id)

    def _override_event(self, item: Instance) -> Event:
        return Event(
            uid=item.uid,
            start=item.start,
            length=sort_key(item.end) - sort_key(item.start),
            summary=item.summary,
            transparency=item.transparency,
            status=item.status,
            tzid=self.master.tzid,
            provider=self.master.provider,
            recurrence_id=item.recurrence_id,
        )

    def events(self) -> list[Event]:
        return [self.master, *(self._override_event(item) for item in self.overrides)]

    def __repr__(self) -> str:
        return f"Series({self.uid!r}, overrides={len(self._overrides)})"
