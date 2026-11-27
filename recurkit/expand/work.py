from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class ExpandedPeriods:
    count: int = 0


_active: list[ExpandedPeriods] = []


@contextmanager
def count_expanded_periods() -> Iterator[ExpandedPeriods]:
    counter = ExpandedPeriods()
    _active.append(counter)
    try:
        yield counter
    finally:
        _active.remove(counter)


def report_expanded_period() -> None:
    for counter in _active:
        counter.count += 1
