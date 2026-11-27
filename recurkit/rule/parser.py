from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

from recurkit.calendar_math import Weekday, is_valid_date
from recurkit.errors import RuleSyntaxError, RuleValidationError
from recurkit.rule.model import Frequency, RuleParts, WeekdayNum

_INTEGER = re.compile(r"[+-]?\d{1,9}", re.ASCII)
_UNSIGNED = re.compile(r"\d{1,9}", re.ASCII)
_WEEKDAY_NUM = re.compile(r"(?P<n>[+-]?\d{1,2})?(?P<day>MO|TU|WE|TH|FR|SA|SU)", re.ASCII)
_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})", re.ASCII)
_DATE_TIME = re.compile(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)", re.ASCII)
_DATE_TIME_WITH_OFFSET = re.compile(r"\d{8}T\d{6}[+-]\d{4}", re.ASCII)


@dataclass(frozen=True)
class _Part:
    name: str
    value: str
    position: int
    value_position: int


def _split_parts(text: str, body: str, offset: int) -> Iterator[_Part]:
    position = offset
    chunks = body.split(";")
    for index, chunk in enumerate(chunks):
        if not chunk:
            if index == len(chunks) - 1 and index > 0:
                return
            raise RuleSyntaxError("empty rule part", text=text, position=position)
        name, sep, value = chunk.partition("=")
        if not sep:
            raise RuleSyntaxError(f"rule part {chunk!r} has no '='", text=text, position=position)
        if not value:
            raise RuleSyntaxError(
                f"rule part {name!r} has an empty value", text=text, position=position
            )
        yield _Part(name.strip(" ").upper(), value.strip(" "), position, position + len(name) + 1)
        position += len(chunk) + 1


def parse_date_or_datetime(value: str) -> date | datetime:
    value = value.strip().upper()
    if _DATE_TIME_WITH_OFFSET.fullmatch(value):
        raise RuleValidationError("DT-03", f"date-time with a UTC offset is not allowed: {value}")
    match = _DATE.fullmatch(value)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if not is_valid_date(year, month, day):
            raise ValueError(f"invalid date {value}")
        return date(year, month, day)
    match = _DATE_TIME.fullmatch(value)
    if not match:
        raise ValueError(f"not a DATE or DATE-TIME value: {value!r}")
    year, month, day, hour, minute, second = (int(g) for g in match.groups()[:6])
    if not is_valid_date(year, month, day):
        raise ValueError(f"invalid date {value}")
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"invalid time {value} (leap seconds are not supported)")
    tzinfo = UTC if match.group(7) else None
    return datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)


class _RuleBuilder:
    def __init__(self, text: str):
        self.text = text
        self.seen: set[str] = set()
        self.freq: Frequency | None = None
        self.interval = 1
        self.count: int | None = None
        self.until: date | datetime | None = None
        self.by_month: tuple[int, ...] = ()
        self.by_week_no: tuple[int, ...] = ()
        self.by_year_day: tuple[int, ...] = ()
        self.by_month_day: tuple[int, ...] = ()
        self.by_day: tuple[WeekdayNum, ...] = ()
        self.by_set_pos: tuple[int, ...] = ()
        self.by_hour: tuple[int, ...] = ()
        self.by_minute: tuple[int, ...] = ()
        self.by_second: tuple[int, ...] = ()
        self.wkst = Weekday.MO

    def error(self, message: str, position: int) -> RuleSyntaxError:
        return RuleSyntaxError(message, text=self.text, position=position)

    def add(self, part: _Part) -> None:
        if part.name in self.seen:
            raise self.error(f"rule part {part.name} is specified twice (RRULE-02)", part.position)
        match part.name:
            case "FREQ":
                self.freq = self._freq(part)
            case "INTERVAL":
                self.interval = self._unsigned(part)
            case "COUNT":
                self.count = self._unsigned(part)
            case "UNTIL":
                self.until = self._until(part)
            case "BYMONTH":
                self.by_month = self._int_list(part)
            case "BYWEEKNO":
                self.by_week_no = self._int_list(part)
            case "BYYEARDAY":
                self.by_year_day = self._int_list(part)
            case "BYMONTHDAY":
                self.by_month_day = self._int_list(part)
            case "BYDAY":
                self.by_day = self._by_day(part)
            case "BYSETPOS":
                self.by_set_pos = self._int_list(part)
            case "BYHOUR":
                self.by_hour = self._int_list(part)
            case "BYMINUTE":
                self.by_minute = self._int_list(part)
            case "BYSECOND":
                self.by_second = self._int_list(part)
            case "WKST":
                self.wkst = self._weekday(part)
            case _:
                raise self.error(f"unknown rule part {part.name!r}", part.position)
        self.seen.add(part.name)

    def build(self, dtstart: date | datetime | None, tzid: str | None) -> RuleParts:
        if self.freq is None:
            raise RuleValidationError("RRULE-01", "the FREQ rule part must be specified")
        return RuleParts(
            freq=self.freq,
            interval=self.interval,
            count=self.count,
            until=self.until,
            by_month=self.by_month,
            by_week_no=self.by_week_no,
            by_year_day=self.by_year_day,
            by_month_day=self.by_month_day,
            by_day=self.by_day,
            by_set_pos=self.by_set_pos,
            wkst=self.wkst,
            dtstart=dtstart,
            tzid=tzid,
            by_hour=self.by_hour,
            by_minute=self.by_minute,
            by_second=self.by_second,
        )

    def _int_list(self, part: _Part) -> tuple[int, ...]:
        result = []
        for item in part.value.split(","):
            if not _INTEGER.fullmatch(item):
                raise self.error(f"{part.name}: {item!r} is not an integer", part.value_position)
            result.append(int(item))
        return tuple(result)

    def _unsigned(self, part: _Part) -> int:
        if not _UNSIGNED.fullmatch(part.value):
            raise self.error(f"{part.name}: {part.value!r} is not a number", part.value_position)
        return int(part.value)

    def _freq(self, part: _Part) -> Frequency:
        try:
            return Frequency(part.value.upper())
        except ValueError:
            raise self.error(f"unknown FREQ value {part.value!r}", part.value_position) from None

    def _until(self, part: _Part) -> date | datetime:
        try:
            return parse_date_or_datetime(part.value)
        except ValueError as exc:
            if isinstance(exc, RuleValidationError):
                raise
            raise self.error(f"UNTIL: {exc}", part.value_position) from None

    def _by_day(self, part: _Part) -> tuple[WeekdayNum, ...]:
        result = []
        for item in part.value.upper().split(","):
            match = _WEEKDAY_NUM.fullmatch(item)
            if not match:
                raise self.error(f"BYDAY: {item!r} is not a weekday", part.value_position)
            n = int(match["n"]) if match["n"] else None
            if n == 0:
                raise RuleValidationError("RRULE-06", "BYDAY ordinal must be 1..53 or -53..-1")
            result.append(WeekdayNum(Weekday.from_code(match["day"]), n))
        return tuple(result)

    def _weekday(self, part: _Part) -> Weekday:
        try:
            return Weekday.from_code(part.value)
        except ValueError:
            raise self.error(
                f"{part.name}: {part.value!r} is not a weekday", part.value_position
            ) from None


def parse_rrule(
    text: str,
    *,
    dtstart: date | datetime | None = None,
    tzid: str | None = None,
) -> RuleParts:
    if not isinstance(text, str):
        raise TypeError("rule text must be a string")
    body = text.strip()
    offset = len(text) - len(text.lstrip())
    if body.upper().startswith("RRULE:"):
        body, offset = body[6:], offset + 6
    if not body:
        raise RuleSyntaxError("empty rule", text=text, position=offset)
    builder = _RuleBuilder(text)
    for part in _split_parts(text, body, offset):
        builder.add(part)
    return builder.build(dtstart, tzid)
