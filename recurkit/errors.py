"""Exception hierarchy of RecurKit.

Every exception raised on purpose by the library derives from RecurKitError,
so callers (and the parser fuzz tests) can catch exactly the library errors.
"""

from __future__ import annotations

import re

_REQUIREMENT_ID = re.compile(r"^[A-Z]+-\d{2}$")


class RecurKitError(Exception):
    """Base class of all RecurKit errors."""


class RuleSyntaxError(RecurKitError, ValueError):
    """The RRULE text cannot be parsed.

    ``position`` is the 0-based offset in ``text`` where the problem starts,
    when it is known.
    """

    def __init__(self, message: str, *, text: str | None = None, position: int | None = None):
        self.message = message
        self.text = text
        self.position = position
        super().__init__(self._format())

    def _format(self) -> str:
        if self.position is None:
            return self.message
        return f"{self.message} (at position {self.position})"


class RuleValidationError(RecurKitError, ValueError):
    """The rule is well-formed but violates a requirement of RFC 5545.

    ``requirement_id`` refers to the catalog in ``docs/requirements.md``,
    for example ``RRULE-07``.
    """

    def __init__(self, requirement_id: str, message: str):
        if not _REQUIREMENT_ID.match(requirement_id):
            raise ValueError(f"malformed requirement id: {requirement_id!r}")
        self.requirement_id = requirement_id
        self.message = message
        super().__init__(f"[{requirement_id}] {message}")


class ICalParseError(RecurKitError, ValueError):
    """iCalendar text cannot be parsed; ``line`` is the 1-based physical line number."""

    def __init__(self, message: str, *, line: int | None = None):
        self.message = message
        self.line = line
        super().__init__(message if line is None else f"line {line}: {message}")


class TimeZoneError(RecurKitError):
    """A time zone is unknown or cannot be applied to a value."""

    def __init__(self, message: str, *, tzid: str | None = None):
        self.message = message
        self.tzid = tzid
        super().__init__(message if tzid is None else f"{message}: {tzid!r}")
