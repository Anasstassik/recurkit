from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from recurkit.errors import ICalParseError

_DURATION = re.compile(
    r"(?P<sign>[+-])?P(?:(?P<weeks>\d+)W|(?P<days>\d+)D(?:T(?P<dtime>.+))?|T(?P<time>.+))"
)
_TIME = re.compile(
    r"(?:(?P<hours>\d+)H(?:(?P<hminutes>\d+)M(?:(?P<hmseconds>\d+)S)?)?"
    r"|(?P<minutes>\d+)M(?:(?P<mseconds>\d+)S)?"
    r"|(?P<seconds>\d+)S)"
)


@dataclass(frozen=True)
class Duration:
    weeks: int = 0
    days: int = 0
    seconds: int = 0
    negative: bool = False

    def __post_init__(self) -> None:
        if min(self.weeks, self.days, self.seconds) < 0:
            raise ValueError("duration parts must not be negative, use negative=True")
        if self.weeks and (self.days or self.seconds):
            raise ValueError("a duration in weeks cannot have days or a time part")

    @property
    def sign(self) -> int:
        return -1 if self.negative else 1

    @property
    def nominal_days(self) -> int:
        return self.sign * (self.weeks * 7 + self.days)

    @property
    def exact(self) -> timedelta:
        return timedelta(seconds=self.sign * self.seconds)

    @property
    def is_whole_days(self) -> bool:
        return self.seconds == 0

    def as_timedelta(self) -> timedelta:
        return timedelta(days=self.nominal_days) + self.exact

    def add_to_local(self, start: date | datetime) -> date | datetime:
        if not isinstance(start, datetime):
            if not self.is_whole_days:
                raise ValueError("a DATE can only be moved by whole days or weeks")
            return start + timedelta(days=self.nominal_days)
        return start + timedelta(days=self.nominal_days) + self.exact


def _number(match: re.Match[str], *names: str) -> int:
    return next((int(value) for name in names if (value := match.group(name)) is not None), 0)


def _time_seconds(text: str, source: str, line: int | None) -> int:
    match = _TIME.fullmatch(text)
    if match is None:
        raise ICalParseError(f"invalid time part in DURATION {source!r}", line=line)
    hours = _number(match, "hours")
    minutes = _number(match, "hminutes", "minutes")
    seconds = _number(match, "hmseconds", "mseconds", "seconds")
    return hours * 3600 + minutes * 60 + seconds


def parse_duration(text: str, line: int | None = None) -> Duration:
    match = _DURATION.fullmatch(text.strip().upper())
    if match is None:
        raise ICalParseError(f"invalid DURATION value {text!r}", line=line)
    time_part = match.group("dtime") or match.group("time")
    return Duration(
        weeks=_number(match, "weeks"),
        days=_number(match, "days"),
        seconds=_time_seconds(time_part, text, line) if time_part else 0,
        negative=match.group("sign") == "-",
    )


def format_duration(duration: Duration) -> str:
    sign = "-" if duration.negative else ""
    if duration.weeks:
        return f"{sign}P{duration.weeks}W"
    hours, rest = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    time = ""
    if hours:
        time = f"{hours}H" + (f"{minutes}M" if minutes or seconds else "")
    elif minutes:
        time = f"{minutes}M"
    if seconds or not (hours or minutes or duration.days):
        time += f"{seconds}S"
    days = f"{duration.days}D" if duration.days else ""
    return f"{sign}P{days}" + (f"T{time}" if time else "")
