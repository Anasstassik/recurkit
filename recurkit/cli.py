from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import TextIO

from recurkit import __version__
from recurkit.errors import RecurKitError, RuleSyntaxError, RuleValidationError
from recurkit.expand import Occurrence
from recurkit.ical import Calendar, Event, parse_ics
from recurkit.rule import Rule, describe, parse_date_or_datetime
from recurkit.series import Series
from recurkit.timezones import TimeZoneProvider, ZoneInfoProvider

_UNTIL = re.compile(r"(?:^|;)\s*UNTIL\s*=\s*([0-9TZ]+)", re.IGNORECASE)


class CliError(Exception): ...


def _default_dtstart(text: str) -> date | datetime:
    match = _UNTIL.search(text)
    if match is None or "T" not in match.group(1).upper():
        return date(1970, 1, 1) if match else datetime(1970, 1, 1)
    if match.group(1).upper().endswith("Z"):
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime(1970, 1, 1)


def _dtstart(value: str | None, text: str) -> date | datetime:
    if value is None:
        return _default_dtstart(text)
    try:
        if "-" not in value:
            return parse_date_or_datetime(value)
        if "T" not in value.upper():
            return date.fromisoformat(value)
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is not None and moment.utcoffset():
            raise ValueError("only floating or UTC (Z) times are allowed, use --tz for a zone")
        return moment.astimezone(UTC) if moment.tzinfo is not None else moment
    except ValueError as exc:
        raise CliError(f"--dtstart: {exc}") from None


def _validate(args: argparse.Namespace, out: TextIO) -> int:
    dtstart = _dtstart(args.dtstart, args.rule)
    if args.tz is not None:
        ZoneInfoProvider().check_zone(args.tz)
    rule = Rule.parse(args.rule, dtstart=dtstart, tzid=args.tz)
    print(f"valid: {rule.to_text()}", file=out)
    print(describe(rule), file=out)
    return 0


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a date like 2026-01-31, got {value!r}"
        ) from None


class _Window:
    def __init__(self, first: date, last: date, tz: str | None, provider: TimeZoneProvider):
        if last < first:
            raise CliError(f"--to {last} is before --from {first}")
        self.days = (first, last + timedelta(days=1))
        self.tz = tz
        self.provider = provider

    def wall(self, day: date) -> datetime:
        return datetime.combine(day, time.min)

    def aware(self, day: date) -> datetime:
        if self.tz is None:
            return self.wall(day).replace(tzinfo=UTC)
        return self.provider.localize(self.tz, self.wall(day))

    def bounds(self, event: Event) -> tuple[Occurrence, Occurrence]:
        first, stop = self.days
        if event.all_day:
            return first, stop
        if isinstance(event.start, datetime) and event.start.tzinfo is None:
            return self.wall(first), self.wall(stop)
        return self.aware(first), self.aware(stop)

    def local(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        if self.tz is None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return self.provider.to_local(self.tz, value)


def _when(window: _Window, start: Occurrence, end: Occurrence) -> str:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        last = end - timedelta(days=1)
        span = f"{start:%Y-%m-%d}" if last <= start else f"{start:%Y-%m-%d}..{last:%Y-%m-%d}"
        return f"{span} all day"
    begin, finish = window.local(start), window.local(end)
    tail = f"{finish:%H:%M}" if finish.date() == begin.date() else f"{finish:%Y-%m-%d %H:%M}"
    return f"{begin:%Y-%m-%d %H:%M}-{tail}"


def _read(path: str, provider: TimeZoneProvider) -> Calendar:
    try:
        text = Path(path).read_text("utf-8")
    except OSError as exc:
        raise CliError(f"cannot read {path}: {exc.strerror}") from None
    try:
        return parse_ics(text, provider=provider)
    except RecurKitError as exc:
        exc.add_note(f"in {path}")
        raise


def _expand(args: argparse.Namespace, out: TextIO) -> int:
    provider = ZoneInfoProvider()
    if args.tz is not None:
        provider.check_zone(args.tz)
    window = _Window(args.first, args.last, args.tz, provider)
    rows: list[str] = []
    for path in args.files:
        for event in _read(path, provider):
            low, high = window.bounds(event)
            if event.is_override:
                if not event.cancelled and low <= event.start < high:
                    rows.append(f"{_when(window, event.start, event.end)}  {event.summary}")
                continue
            if event.cancelled:
                continue
            for item in Series.from_event(event).between(low, high):
                rows.append(f"{_when(window, item.start, item.end)}  {item.summary}")
    for row in sorted(rows):
        print(row, file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recurkit", description="RFC 5545 recurrence rules from the command line."
    )
    parser.add_argument("--version", action="version", version=f"recurkit {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    validate = commands.add_parser("validate", help="check one RRULE value and describe it")
    validate.add_argument("rule", help='rule text, e.g. "FREQ=MONTHLY;BYDAY=2TU;COUNT=6"')
    validate.add_argument(
        "--dtstart", help="DTSTART as 20260106T100000, 2026-01-06T10:00 or a date"
    )
    validate.add_argument("--tz", help="TZID of DTSTART, e.g. Europe/Kyiv")
    validate.set_defaults(handler=_validate)
    expand = commands.add_parser("expand", help="list event instances of .ics files in a window")
    expand.add_argument("files", nargs="+", help=".ics files")
    expand.add_argument("--from", dest="first", type=_day, required=True, help="first day")
    expand.add_argument("--to", dest="last", type=_day, required=True, help="last day, inclusive")
    expand.add_argument("--tz", help="time zone to show times in (default: UTC)")
    expand.set_defaults(handler=_expand)
    return parser


def _describe_error(exc: RecurKitError | CliError) -> str:
    if isinstance(exc, RuleValidationError):
        return f"invalid: [{exc.requirement_id}] {exc.message}"
    if isinstance(exc, RuleSyntaxError):
        return f"syntax error: {exc}"
    return f"error: {exc}"


def main(
    argv: Sequence[str] | None = None, *, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    stdout = out if out is not None else sys.stdout
    stderr = err if err is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        code: int = args.handler(args, stdout)
    except (RecurKitError, CliError) as exc:
        print(f"recurkit: {_describe_error(exc)}", file=stderr)
        for note in getattr(exc, "__notes__", []):
            print(f"  {note}", file=stderr)
        return 1
    return code
