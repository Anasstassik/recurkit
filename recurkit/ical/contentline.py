"""Content lines of iCalendar text (RFC 5545, section 3.1).

A content line is ``NAME;PARAM=value;PARAM="quoted,value":VALUE``. Long
lines are folded: a line break followed by one space or tab continues the
previous line. This module unfolds the text and splits each line into its
name, parameters and value; it does not interpret values.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from recurkit.errors import ICalParseError

_NAME = re.compile(r"[A-Za-z0-9-]+")
_SAFE_CHAR = re.compile(r'[^";:,\x00-\x08\x0a-\x1f\x7f]*')
_QSAFE_CHAR = re.compile(r'[^"\x00-\x08\x0a-\x1f\x7f]*')


@dataclass(frozen=True)
class ContentLine:
    """One unfolded content line; names are upper-case, ``line`` is where it starts."""

    name: str
    value: str
    params: dict[str, tuple[str, ...]] = field(default_factory=dict)
    line: int = 0

    def param(self, name: str) -> str | None:
        """The single value of a parameter, or ``None`` if it is absent."""
        values = self.params.get(name.upper())
        if values is None:
            return None
        if len(values) != 1:
            raise ICalParseError(f"parameter {name} must have one value", line=self.line)
        return values[0]


def unfold(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line_number, logical_line)`` pairs; empty lines are skipped.

    Both CRLF and bare LF line breaks are accepted. A line that starts with a
    space or a tab continues the previous one (the first character is removed).
    """
    current: list[str] = []
    start = 0
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if raw[:1] in (" ", "\t"):
            if not current:
                raise ICalParseError("continuation line without a line to continue", line=number)
            current.append(raw[1:])
            continue
        if current:
            yield start, "".join(current)
        current, start = ([raw], number) if raw else ([], number)
    if current:
        yield start, "".join(current)


class _LineReader:
    def __init__(self, text: str, line: int):
        self.text = text
        self.pos = 0
        self.line = line

    def error(self, message: str) -> ICalParseError:
        return ICalParseError(f"{message} (column {self.pos + 1})", line=self.line)

    def take(self, pattern: re.Pattern[str]) -> str:
        match = pattern.match(self.text, self.pos)
        assert match is not None  # the patterns used here match the empty string
        self.pos = match.end()
        return match.group()

    def name(self) -> str:
        match = _NAME.match(self.text, self.pos)
        if match is None:
            raise self.error("expected a name")
        self.pos = match.end()
        return match.group().upper()

    def expect(self, char: str) -> None:
        if not self.text.startswith(char, self.pos):
            raise self.error(f"expected {char!r}")
        self.pos += 1

    def peek(self) -> str:
        return self.text[self.pos : self.pos + 1]

    def param_value(self) -> str:
        if self.peek() == '"':
            self.pos += 1
            value = self.take(_QSAFE_CHAR)
            self.expect('"')
            return value
        return self.take(_SAFE_CHAR)


def parse_content_line(text: str, line: int = 0) -> ContentLine:
    """Split one unfolded line into name, parameters and value."""
    reader = _LineReader(text, line)
    name = reader.name()
    params: dict[str, tuple[str, ...]] = {}
    while reader.peek() == ";":
        reader.pos += 1
        param = reader.name()
        reader.expect("=")
        values = [reader.param_value()]
        while reader.peek() == ",":
            reader.pos += 1
            values.append(reader.param_value())
        if param in params:
            raise reader.error(f"parameter {param} is repeated")
        params[param] = tuple(values)
    reader.expect(":")
    return ContentLine(name, text[reader.pos :], params, line)


def parse_content_lines(text: str) -> list[ContentLine]:
    """Unfold ``text`` and parse every content line in it."""
    return [parse_content_line(logical, number) for number, logical in unfold(text)]


def unescape_text(value: str) -> str:
    """Decode a TEXT value: ``\\\\`` ``\\;`` ``\\,`` and ``\\n`` / ``\\N``."""
    result: list[str] = []
    chars = iter(value)
    for char in chars:
        if char != "\\":
            result.append(char)
            continue
        escaped = next(chars, "")
        if escaped in ("n", "N"):
            result.append("\n")
        elif escaped in ("\\", ";", ","):
            result.append(escaped)
        else:
            raise ICalParseError(f"invalid escape sequence \\{escaped} in TEXT value")
    return "".join(result)


def split_values(value: str) -> list[str]:
    """Split a comma-separated multi-value property such as RDATE or EXDATE."""
    return [item.strip() for item in value.split(",") if item.strip()]
