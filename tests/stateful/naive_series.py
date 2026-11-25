from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

Row = tuple[datetime, datetime, str, str, bool]


@dataclass(frozen=True)
class NaiveInstance:
    uid: str
    recurrence_id: datetime
    start: datetime
    end: datetime
    summary: str
    cancelled: bool = False

    def row(self) -> Row:
        return self.start, self.recurrence_id, self.uid, self.summary, self.cancelled


class NaiveSeries:
    def __init__(self, uid: str, starts: list[datetime], length: timedelta, summary: str):
        self.plain = {s: NaiveInstance(uid, s, s, s + length, summary) for s in starts}
        self.items = dict(self.plain)

    def ids(self) -> list[datetime]:
        return sorted(self.items)

    def owner(self, recurrence_id: datetime) -> str:
        return self.items[recurrence_id].uid

    def first_of(self, uid: str) -> datetime:
        return min(rid for rid, item in self.items.items() if item.uid == uid)

    def override(self, recurrence_id: datetime, shift: timedelta, summary: str) -> None:
        item = self.items[recurrence_id]
        self.items[recurrence_id] = replace(
            item, start=item.start + shift, end=item.end + shift, summary=summary
        )

    def cancel(self, recurrence_id: datetime) -> None:
        self.items[recurrence_id] = replace(self.items[recurrence_id], cancelled=True)

    def restore(self, recurrence_id: datetime) -> None:
        self.items[recurrence_id] = self.plain[recurrence_id]

    def split(self, at: datetime, uid: str) -> None:
        owner = self.owner(at)
        for table in (self.plain, self.items):
            for rid, item in table.items():
                if rid >= at and item.uid == owner:
                    table[rid] = replace(item, uid=uid)

    def rows(self) -> list[Row]:
        return sorted(item.row() for item in self.items.values())
