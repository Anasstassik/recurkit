from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, time

from recurkit.expand.iterator import (
    Occurrence,
    ValidityCheck,
    effective_until,
    occurrences,
    require_floating,
)
from recurkit.expand.jump import candidates_from
from recurkit.rule.model import Rule


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
    return _window(candidates_from(rule, low, is_valid=is_valid, until=stop), low, high, inclusive)


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
    for value in candidates_from(rule, bound, is_valid=is_valid, until=until):
        if _after_or_at(value, bound, inclusive):
            return value
    return None


def before(
    rule: Rule,
    moment: Occurrence,
    *,
    inclusive: bool = False,
    is_valid: ValidityCheck | None = None,
    until: Occurrence | None = None,
) -> Occurrence | None:
    bound = coerce_bound(rule, moment)
    last: Occurrence | None = None
    for value in occurrences(rule, is_valid=is_valid, until=until):
        if not _before_or_at(value, bound, inclusive):
            break
        last = value
    return last


def is_occurrence(rule: Rule, moment: Occurrence, *, is_valid: ValidityCheck | None = None) -> bool:
    return after(rule, moment, inclusive=True, is_valid=is_valid) == coerce_bound(rule, moment)
