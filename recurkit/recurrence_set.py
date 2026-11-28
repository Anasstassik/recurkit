from __future__ import annotations

import heapq
from bisect import bisect_left
from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, time
from enum import Enum

from recurkit.errors import RuleValidationError
from recurkit.expand import (
    Occurrence,
    ValidityCheck,
    can_jump,
    candidates,
    first_span,
    last_in_windows,
    last_value,
)
from recurkit.rule.model import Rule
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider
from recurkit.timezones.frame import ZoneFrame


class ValueKind(Enum):
    ALL_DAY = "all-day"
    FLOATING = "floating"
    UTC = "utc"
    ZONED = "zoned"

    @classmethod
    def of(cls, dtstart: Occurrence, tzid: str | None) -> ValueKind:
        if not isinstance(dtstart, datetime):
            return cls.ALL_DAY
        if tzid is not None:
            return cls.ZONED
        return cls.FLOATING if dtstart.tzinfo is None else cls.UTC

    def accepts(self, value: Occurrence) -> bool:
        if not isinstance(value, datetime):
            return self is ValueKind.ALL_DAY
        if self is ValueKind.FLOATING:
            return value.tzinfo is None
        return self is ValueKind.ZONED or (self is ValueKind.UTC and value.tzinfo is not None)


def unique_sorted(values: Iterable[Occurrence]) -> list[Occurrence]:
    return sorted(set(values))


def merge_unique(*streams: Iterable[Occurrence]) -> Iterator[Occurrence]:
    previous: Occurrence | None = None
    for value in heapq.merge(*streams):
        if value != previous:
            yield value
            previous = value


class RecurrenceSet:
    def __init__(
        self,
        rule: Rule,
        rdates: Iterable[Occurrence] = (),
        exdates: Iterable[Occurrence] = (),
        *,
        provider: TimeZoneProvider | None = None,
    ):
        self.rule = rule
        dtstart = rule.require_dtstart()
        self.kind = ValueKind.of(dtstart, rule.tzid)
        self.frame: ZoneFrame | None = None
        if rule.tzid is not None:
            self.frame = ZoneFrame(
                provider if provider is not None else ZoneInfoProvider(), rule.tzid
            )
        explicit = (tuple(rdates), tuple(exdates))
        for value in (*explicit[0], *explicit[1]):
            if not self.kind.accepts(value):
                raise RuleValidationError(
                    "RSET-04", f"{value!r} is not the same kind of value as DTSTART {dtstart!r}"
                )
        self._until = self._until_instant()
        self.local_rule = self._local_rule()
        self.rdates = tuple(unique_sorted(self._place(v) for v in explicit[0]))
        self.exdates = frozenset(self._place(v) for v in explicit[1])

    @property
    def tzid(self) -> str | None:
        return None if self.frame is None else self.frame.tzid

    @property
    def provider(self) -> TimeZoneProvider | None:
        return None if self.frame is None else self.frame.provider

    @property
    def zoned(self) -> bool:
        return self.kind is ValueKind.ZONED

    def _place(self, value: Occurrence) -> Occurrence:
        if self.frame is not None and isinstance(value, datetime):
            return self.frame.place(value)
        if self.kind is ValueKind.UTC and isinstance(value, datetime):
            return value.astimezone(UTC)
        return value

    def _until_instant(self) -> datetime | None:
        until = self.rule.until
        if self.frame is not None and isinstance(until, datetime) and until.tzinfo is not None:
            return until
        return None

    def _local_rule(self) -> Rule:
        until = self.rule.until
        if self.frame is not None and self._until is not None:
            until = self.frame.local_window(None, self._until)[1]
        return replace(self.rule, until=until, tzid=None)

    def _rule_values(
        self, start: Occurrence | None = None, stop: Occurrence | None = None
    ) -> Iterator[Occurrence]:
        is_valid = None if self.frame is None else self._exists_check(self.frame)
        for local in candidates(self.local_rule, start, is_valid=is_valid, until=stop):
            value = self._place(local)
            if self._until is not None and value > self._until:
                return
            yield value

    def _exists_check(self, frame: ZoneFrame) -> ValidityCheck:
        dtstart = self.rule.require_dtstart()
        first = dtstart
        if isinstance(dtstart, datetime) and not frame.exists(dtstart):
            first = frame.place(dtstart).replace(tzinfo=None)

        def exists(local: Occurrence) -> bool:
            if local == dtstart or not isinstance(local, datetime):
                return True
            return local > first and frame.exists(local)

        return exists

    def _values(
        self, start: Occurrence | None = None, stop: Occurrence | None = None
    ) -> Iterator[Occurrence]:
        rdates: Iterable[Occurrence] = self.rdates
        if start is not None:
            rdates = self.rdates[bisect_left(self.rdates, start) :]
        local_start, local_stop = start, stop
        if self.frame is not None:
            local_start, local_stop = self.frame.local_window(start, stop)
        for value in merge_unique(self._rule_values(local_start, local_stop), rdates):
            if value not in self.exdates:
                yield value

    def coerce(self, bound: Occurrence) -> Occurrence:
        dtstart = self.rule.require_dtstart()
        if not isinstance(dtstart, datetime):
            return bound.date() if isinstance(bound, datetime) else bound
        if not isinstance(bound, datetime):
            bound = datetime.combine(bound, time.min, tzinfo=dtstart.tzinfo)
        if self.kind is ValueKind.ZONED:
            return self._place(bound)
        if not self.kind.accepts(bound):
            raise TypeError("query bound and DTSTART must both be naive or both be aware")
        return bound

    def occurrences(self) -> Iterator[Occurrence]:
        return self._values()

    __iter__ = occurrences

    def between(
        self, start: Occurrence, end: Occurrence, *, inclusive: bool = True
    ) -> Iterator[Occurrence]:
        low, high = self.coerce(start), self.coerce(end)
        if high < low:
            raise ValueError("the end of the window is before its start")
        for value in self._values(low, high):
            if value > high or (not inclusive and value == high):
                return
            if value > low or (inclusive and value == low):
                yield value

    def after(self, moment: Occurrence, *, inclusive: bool = False) -> Occurrence | None:
        bound = self.coerce(moment)
        for value in self._values(bound):
            if value > bound or (inclusive and value == bound):
                return value
        return None

    def before(self, moment: Occurrence, *, inclusive: bool = False) -> Occurrence | None:
        bound = self.coerce(moment)
        if not can_jump(self.rule):
            walk = self._values(None, bound)
            return last_value(v for v in walk if self._below(v, bound, inclusive))

        def window(low: Occurrence) -> Iterator[Occurrence]:
            return (v for v in self.between(low, bound) if self._below(v, bound, inclusive))

        return last_in_windows(window, self._earliest(), bound, first_span(self.rule))

    @staticmethod
    def _below(value: Occurrence, bound: Occurrence, inclusive: bool) -> bool:
        return value < bound or (inclusive and value == bound)

    def _earliest(self) -> Occurrence:
        start = self._place(self.rule.require_dtstart())
        return min(start, self.rdates[0]) if self.rdates else start

    def __repr__(self) -> str:
        zone = f", tzid={self.tzid!r}" if self.tzid else ""
        return (
            f"RecurrenceSet({self.rule.to_text()!r}, dtstart={self.rule.dtstart!r}{zone}, "
            f"rdates={len(self.rdates)}, exdates={len(self.exdates)})"
        )
