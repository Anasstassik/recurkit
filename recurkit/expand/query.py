"""Window queries over a rule: ``between``, ``after`` and ``before``.

The occurrences of a rule are increasing, so a query can stop as soon as it
passes the end of its window.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, time

from recurkit.expand.iterator import Occurrence, ValidityCheck, occurrences
from recurkit.rule.model import Rule


def coerce_bound(rule: Rule, bound: Occurrence) -> Occurrence:
    """Bring a query bound to the value type of the rule's occurrences.

    - an all-day rule compares calendar days, so a ``datetime`` bound becomes
      its date;
    - a timed rule given a ``date`` bound uses midnight of that day;
    - a naive bound is not comparable with a UTC rule, and vice versa.
    """
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
    """Occurrences in the window from ``start`` to ``end``.

    Both bounds are included by default; ``inclusive=False`` excludes them.
    """
    low, high = coerce_bound(rule, start), coerce_bound(rule, end)
    if high < low:
        raise ValueError("the end of the window is before its start")
    for value in occurrences(rule, is_valid=is_valid, until=until):
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
    """The first occurrence strictly after ``moment`` (or at it, if ``inclusive``)."""
    bound = coerce_bound(rule, moment)
    for value in occurrences(rule, is_valid=is_valid, until=until):
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
    """The last occurrence strictly before ``moment`` (or at it, if ``inclusive``)."""
    bound = coerce_bound(rule, moment)
    last: Occurrence | None = None
    for value in occurrences(rule, is_valid=is_valid, until=until):
        if not _before_or_at(value, bound, inclusive):
            break
        last = value
    return last


def is_occurrence(rule: Rule, moment: Occurrence, *, is_valid: ValidityCheck | None = None) -> bool:
    """True if ``moment`` is exactly one of the rule's occurrences."""
    return after(rule, moment, inclusive=True, is_valid=is_valid) == coerce_bound(rule, moment)
