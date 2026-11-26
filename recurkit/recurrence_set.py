from __future__ import annotations

import heapq
from bisect import bisect_left
from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, timezone

from recurkit.errors import RuleValidationError, TimeZoneError
from recurkit.expand import Occurrence, ValidityCheck
from recurkit.expand import occurrences as rule_occurrences
from recurkit.expand.jump import candidates_from
from recurkit.rule.model import Rule
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider
from recurkit.timezones.provider import out_of_range, probe

_MARGIN = timedelta(days=1)


def unique_sorted(values: Iterable[Occurrence]) -> list[Occurrence]:
    return sorted(set(values))


def merge_unique(*streams: Iterable[Occurrence]) -> Iterator[Occurrence]:
    previous: Occurrence | None = None
    for value in heapq.merge(*streams):
        if value != previous:
            yield value
            previous = value


def _same_kind(value: Occurrence, reference: Occurrence, zoned: bool) -> bool:
    if isinstance(reference, datetime):
        if not isinstance(value, datetime):
            return False
        return zoned or (value.tzinfo is None) == (reference.tzinfo is None)
    return isinstance(value, date) and not isinstance(value, datetime)


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
        self.tzid = rule.tzid
        self.provider: TimeZoneProvider | None = None
        if self.tzid is not None:
            self.provider = provider if provider is not None else ZoneInfoProvider()
            self.provider.check_zone(self.tzid)
        explicit = (tuple(rdates), tuple(exdates))
        for value in (*explicit[0], *explicit[1]):
            if not _same_kind(value, dtstart, self.zoned):
                raise RuleValidationError(
                    "RSET-04", f"{value!r} is not the same kind of value as DTSTART {dtstart!r}"
                )
        self.local_rule = self._local_rule()
        self.rdates = tuple(unique_sorted(self._place(v) for v in explicit[0]))
        self.exdates = frozenset(self._place(v) for v in explicit[1])

    @property
    def zoned(self) -> bool:
        return self.tzid is not None

    def _zone(self) -> tuple[TimeZoneProvider, str]:
        if self.provider is None or self.tzid is None:
            raise TimeZoneError("the rule has no TZID")
        return self.provider, self.tzid

    def _place(self, value: Occurrence) -> Occurrence:
        if not isinstance(value, datetime):
            return value
        if not self.zoned:
            return value if value.tzinfo is None else value.astimezone(UTC)
        provider, tzid = self._zone()
        if value.tzinfo is None:
            return provider.localize(tzid, value)
        try:
            return value.astimezone(timezone(provider.utc_offset(tzid, value), tzid))
        except OverflowError as error:
            raise out_of_range(tzid) from error

    def _local_rule(self) -> Rule:
        until = self.rule.until
        if self.zoned and isinstance(until, datetime) and until.tzinfo is not None:
            provider, tzid = self._zone()
            until = provider.to_local(tzid, until)
        return replace(self.rule, until=until, tzid=None)

    def _rule_values(
        self, start: Occurrence | None = None, stop: Occurrence | None = None
    ) -> Iterator[Occurrence]:
        is_valid = self._exists_check() if self.zoned else None
        source = (
            rule_occurrences(self.local_rule, is_valid=is_valid, until=stop)
            if start is None
            else candidates_from(self.local_rule, start, is_valid=is_valid, until=stop)
        )
        for local in source:
            yield self._place(local)

    def _exists_check(self) -> ValidityCheck:
        provider, tzid = self._zone()
        dtstart = self.rule.require_dtstart()

        def exists(local: Occurrence) -> bool:
            if local == dtstart or not isinstance(local, datetime):
                return True
            return provider.exists(tzid, local)

        return exists

    def _values(
        self, start: Occurrence | None = None, stop: Occurrence | None = None
    ) -> Iterator[Occurrence]:
        rdates: Iterable[Occurrence] = self.rdates
        if start is not None:
            rdates = self.rdates[bisect_left(self.rdates, start) :]
        local_start = None if start is None else self._local(start, -_MARGIN)
        local_stop = None if stop is None else self._local(stop, _MARGIN)
        for value in merge_unique(self._rule_values(local_start, local_stop), rdates):
            if value not in self.exdates:
                yield value

    def _local(self, bound: Occurrence, margin: timedelta) -> Occurrence:
        if isinstance(bound, datetime) and self.zoned:
            provider, tzid = self._zone()
            local = provider.to_local(tzid, bound).replace(tzinfo=UTC)
            return probe(local, margin).replace(tzinfo=None)
        return bound

    def coerce(self, bound: Occurrence) -> Occurrence:
        dtstart = self.rule.require_dtstart()
        if not isinstance(dtstart, datetime):
            return bound.date() if isinstance(bound, datetime) else bound
        if not isinstance(bound, datetime):
            bound = datetime.combine(bound, time.min, tzinfo=dtstart.tzinfo)
        if self.zoned:
            return self._place(bound)
        if (bound.tzinfo is None) != (dtstart.tzinfo is None):
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
        last: Occurrence | None = None
        for value in self._values():
            if value > bound or (not inclusive and value == bound):
                break
            last = value
        return last

    def __repr__(self) -> str:
        zone = f", tzid={self.tzid!r}" if self.tzid else ""
        return (
            f"RecurrenceSet({self.rule.to_text()!r}, dtstart={self.rule.dtstart!r}{zone}, "
            f"rdates={len(self.rdates)}, exdates={len(self.exdates)})"
        )
