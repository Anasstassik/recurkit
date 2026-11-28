from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from recurkit.timezones.provider import TimeZoneProvider, out_of_range, probe

_REACH = timedelta(days=1)


@dataclass(frozen=True)
class ZoneFrame:
    provider: TimeZoneProvider
    tzid: str

    def __post_init__(self) -> None:
        self.provider.check_zone(self.tzid)

    def place(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return self.provider.localize(self.tzid, value)
        try:
            return value.astimezone(timezone(self.provider.utc_offset(self.tzid, value), self.tzid))
        except OverflowError as error:
            raise out_of_range(self.tzid) from error

    def to_local(self, instant: datetime) -> datetime:
        return self.provider.to_local(self.tzid, instant)

    def exists(self, local: datetime) -> bool:
        return self.provider.exists(self.tzid, local)

    def local_window(self, low: date | None, high: date | None) -> tuple[date | None, date | None]:
        return self._local(low, -1), self._local(high, 1)

    def margin(self, bound: datetime, sign: int) -> timedelta:
        here = self.provider.utc_offset(self.tzid, bound)
        there = self.provider.utc_offset(self.tzid, probe(bound, -sign * _REACH))
        return max(timedelta(0), sign * (there - here))

    def _local(self, bound: date | None, sign: int) -> date | None:
        if not isinstance(bound, datetime):
            return bound
        local = self.to_local(bound).replace(tzinfo=UTC)
        return probe(local, sign * self.margin(bound, sign)).replace(tzinfo=None)
