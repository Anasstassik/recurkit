from __future__ import annotations

import heapq
from collections.abc import Iterable, Iterator
from dataclasses import replace

from recurkit.errors import SeriesError
from recurkit.expand import Occurrence
from recurkit.ical import Event
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

    def __repr__(self) -> str:
        return f"Series({self.uid!r}, overrides={len(self._overrides)})"
