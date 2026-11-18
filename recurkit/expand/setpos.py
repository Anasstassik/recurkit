"""BYSETPOS: pick occurrences by position within one period (RRULE-22).

RFC 5545 example: "the last work day of the month" is
``FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1``. BYSETPOS is applied after
all other BYxxx parts and before COUNT and UNTIL (RRULE-17).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date


def resolve_position(position: int, size: int) -> int | None:
    """0-based index of a BYSETPOS value in a set of ``size`` items.

    1 is the first item, -1 the last. ``None`` if the set has no such item.
    """
    if position == 0:
        raise ValueError("BYSETPOS value must not be zero")
    index = position - 1 if position > 0 else size + position
    if 0 <= index < size:
        return index
    return None


def apply_set_pos(candidates: Sequence[date], positions: Sequence[int]) -> list[date]:
    """Select the BYSETPOS positions from the sorted candidates of one period.

    Positions outside the set are ignored. The result is sorted and has no
    duplicates even if two positions name the same item (``1`` and ``-3`` in
    a set of three).
    """
    if not positions:
        return list(candidates)
    size = len(candidates)
    chosen = set()
    for position in positions:
        index = resolve_position(position, size)
        if index is not None:
            chosen.add(index)
    return [candidates[index] for index in sorted(chosen)]
