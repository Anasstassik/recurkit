from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from recurkit.errors import SeriesError
from recurkit.expand import Occurrence
from recurkit.ical import Event
from recurkit.recurrence_set import RecurrenceSet
from recurkit.rule import Rule
from recurkit.series.instance import same_kind
from recurkit.series.series import Series


def _until(value: Occurrence) -> Occurrence:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC)
    return value


def _local(recurrence: RecurrenceSet, value: Occurrence) -> Occurrence:
    if recurrence.frame is None or not isinstance(value, datetime):
        return value
    return recurrence.frame.to_local(value)


def _part(
    master: Event,
    recurrence: RecurrenceSet,
    rule: Rule,
    rdates: list[Occurrence],
    exdates: list[Occurrence],
) -> Event:
    return replace(
        master,
        recurrence=RecurrenceSet(rule, rdates, exdates, provider=recurrence.provider),
        rdates=tuple(rdates),
        exdates=frozenset(exdates),
        overrides=(),
    )


def _before(event: Event, at: Occurrence) -> bool:
    return event.recurrence_id is not None and event.recurrence_id < at


def split(series: Series, at: Occurrence, *, uid: str) -> tuple[Series, Series]:
    master = series.master
    recurrence = master.recurrence
    if recurrence is None:
        raise SeriesError(f"{series.uid} has no RRULE to split", uid=series.uid)
    if uid == series.uid:
        raise SeriesError(f"the new series needs a UID other than {uid}", uid=series.uid)
    rule_values = RecurrenceSet(recurrence.rule, provider=recurrence.provider)
    if not same_kind(at, master.start) or rule_values.after(at, inclusive=True) != at:
        raise SeriesError(f"{at!r} is not an instance of the rule of {series.uid}", uid=series.uid)
    last = rule_values.before(at)
    if last is None:
        raise SeriesError(f"{at!r} is the first instance of {series.uid}", uid=series.uid)
    rule = recurrence.rule
    start = _local(recurrence, at)
    if rule.count is None:
        head_rule = replace(rule, until=_until(last))
        tail_rule = replace(rule, dtstart=start)
    else:
        before = sum(1 for _ in rule_values.between(master.start, last))
        head_rule = replace(rule, count=before)
        tail_rule = replace(rule, dtstart=start, count=rule.count - before)
    head = _part(
        master,
        recurrence,
        head_rule,
        [v for v in recurrence.rdates if v < at],
        [v for v in recurrence.exdates if v < at],
    )
    tail = _part(
        master,
        recurrence,
        tail_rule,
        [v for v in recurrence.rdates if v > at],
        [v for v in recurrence.exdates if v >= at],
    )
    overrides = series.events()[1:]
    early = [event for event in overrides if _before(event, at)]
    late = [replace(event, uid=uid) for event in overrides if not _before(event, at)]
    return Series(head, early), Series(replace(tail, uid=uid, start=recurrence.coerce(at)), late)
