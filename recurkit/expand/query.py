from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, time, timedelta

from recurkit.expand.iterator import (
    Occurrence,
    ValidityCheck,
    effective_until,
    occurrences,
    require_floating,
)
from recurkit.expand.jump import can_jump, candidates
from recurkit.expand.subdaily import UNITS
from recurkit.rule.model import Rule

_FIRST_SPAN = timedelta(days=8)
_FIRST_PERIODS = 8


def first_span(rule: Rule) -> timedelta:
    unit = UNITS.get(rule.freq)
    return _FIRST_SPAN if unit is None else unit * rule.interval * _FIRST_PERIODS


def coerce_bound(rule: Rule, bound: Occurrence) -> Occurrence:
    require_floating(rule)
    dtstart = rule.require_dtstart()
    if not isinstance(dtstart, datetime):
        return bound.date() if isinstance(bound, datetime) else bound
    if not isinstance(bound, datetime):
        return datetime.combine(bound, time.min, tzinfo=dtstart.tzinfo)
    if (bound.tzinfo is None) != (dtstart.tzinfo is None):
        raise TypeError("query bound and DTSTART must both be naive or both be aware")
    return bound


def _before_or_at(value: Occurrence, bound: Occurrence, inclusive: bool) -> bool:
    return value <= bound if inclusive else value < bound


def _after_or_at(value: Occurrence, bound: Occurrence, inclusive: bool) -> bool:
    return value >= bound if inclusive else value > bound


def between(
    rule: Rule,
    start: Occurrence,
    end: Occurrence,
    *,
    inclusive: bool = True,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Iterator[Occurrence]:
    low, high = coerce_bound(rule, start), coerce_bound(rule, end)
    if high < low:
        raise ValueError("the end of the window is before its start")
    rule_bound = effective_until(rule, until)
    stop = high if rule_bound is None else min(rule_bound, high)
    return _window(candidates(rule, low, is_valid=is_valid, until=stop), low, high, inclusive)


def _window(
    values: Iterator[Occurrence], low: Occurrence, high: Occurrence, inclusive: bool
) -> Iterator[Occurrence]:
    for value in values:
        if not _before_or_at(value, high, inclusive):
            return
        if _after_or_at(value, low, inclusive):
            yield value


def after(
    rule: Rule,
    moment: Occurrence,
    *,
    inclusive: bool = False,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Occurrence | None:
    bound = coerce_bound(rule, moment)
    for value in candidates(rule, bound, is_valid=is_valid, until=until):
        if _after_or_at(value, bound, inclusive):
            return value
    return None


def last_value(values: Iterable[Occurrence]) -> Occurrence | None:
    last: Occurrence | None = None
    for value in values:
        last = value
    return last


def _back(bound: Occurrence, span: timedelta, earliest: Occurrence) -> Occurrence:
    try:
        return max(bound - span, earliest)
    except OverflowError:
        return earliest


def last_in_windows(
    window: Callable[[Occurrence], Iterable[Occurrence]],
    earliest: Occurrence,
    bound: Occurrence,
    span: timedelta = _FIRST_SPAN,
) -> Occurrence | None:
    if bound < earliest:
        return None
    while True:
        low = _back(bound, span, earliest)
        found = last_value(window(low))
        if found is not None or low == earliest:
            return found
        span *= 2


def before(
    rule: Rule,
    moment: Occurrence,
    *,
    inclusive: bool = False,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Occurrence | None:
    bound = coerce_bound(rule, moment)
    if not can_jump(rule):
        walk = occurrences(rule, is_valid=is_valid, until=until)
        return last_value(_until_bound(walk, bound, inclusive))

    def window(low: Occurrence) -> Iterator[Occurrence]:
        values = between(rule, low, bound, is_valid=is_valid, until=until)
        return _until_bound(values, bound, inclusive)

    earliest = coerce_bound(rule, rule.require_dtstart())
    return last_in_windows(window, earliest, bound, first_span(rule))


def _until_bound(
    values: Iterable[Occurrence], bound: Occurrence, inclusive: bool
) -> Iterator[Occurrence]:
    for value in values:
        if not _before_or_at(value, bound, inclusive):
            return
        yield value


def is_occurrence(rule: Rule, moment: Occurrence, *, is_valid: ValidityCheck | None = None) -> bool:
    return after(rule, moment, inclusive=True, is_valid=is_valid) == coerce_bound(rule, moment)
