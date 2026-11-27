from __future__ import annotations

from collections.abc import Sequence


def resolve_position(position: int, size: int) -> int | None:
    if position == 0:
        raise ValueError("BYSETPOS value must not be zero")
    index = position - 1 if position > 0 else size + position
    if 0 <= index < size:
        return index
    return None


def apply_set_pos[T](candidates: Sequence[T], positions: Sequence[int]) -> list[T]:
    if not positions:
        return list(candidates)
    size = len(candidates)
    chosen = set()
    for position in positions:
        index = resolve_position(position, size)
        if index is not None:
            chosen.add(index)
    return [candidates[index] for index in sorted(chosen)]
