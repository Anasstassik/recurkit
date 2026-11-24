from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import TextIO

from recurkit import __version__
from recurkit.errors import RecurKitError, RuleSyntaxError, RuleValidationError
from recurkit.rule import Rule, describe, parse_date_or_datetime
from recurkit.timezones import ZoneInfoProvider

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
        return 1
    return code
