from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from recurkit.errors import ICalParseError
from recurkit.ical.contentline import ContentLine, parse_content_lines


@dataclass
class Component:
    name: str
    line: int = 0
    properties: list[ContentLine] = field(default_factory=list)
    children: list[Component] = field(default_factory=list)

    def all(self, name: str) -> list[ContentLine]:
        wanted = name.upper()
        return [prop for prop in self.properties if prop.name == wanted]

    def first(self, name: str) -> ContentLine | None:
        found = self.all(name)
        if len(found) > 1:
            raise ICalParseError(
                f"{name.upper()} must appear only once in {self.name}", line=found[1].line
            )
        return found[0] if found else None

    def required(self, name: str) -> ContentLine:
        found = self.first(name)
        if found is None:
            raise ICalParseError(f"{self.name} has no {name.upper()}", line=self.line)
        return found

    def components(self, name: str) -> list[Component]:
        wanted = name.upper()
        return [child for child in self.children if child.name == wanted]

    def walk(self) -> Iterator[Component]:
        yield self
        for child in self.children:
            yield from child.walk()


def _component_name(line: ContentLine) -> str:
    name = line.value.strip().upper()
    if not name or line.params:
        raise ICalParseError(f"{line.name} needs a plain component name", line=line.line)
    return name


def build_components(lines: list[ContentLine]) -> list[Component]:
    roots: list[Component] = []
    stack: list[Component] = []
    for line in lines:
        if line.name == "BEGIN":
            component = Component(_component_name(line), line.line)
            (stack[-1].children if stack else roots).append(component)
            stack.append(component)
        elif line.name == "END":
            name = _component_name(line)
            if not stack:
                raise ICalParseError(f"END:{name} without BEGIN:{name}", line=line.line)
            if stack[-1].name != name:
                raise ICalParseError(
                    f"END:{name} closes BEGIN:{stack[-1].name} from line {stack[-1].line}",
                    line=line.line,
                )
            stack.pop()
        elif stack:
            stack[-1].properties.append(line)
        else:
            raise ICalParseError(f"{line.name} is outside of any component", line=line.line)
    if stack:
        raise ICalParseError(f"BEGIN:{stack[-1].name} is never closed", line=stack[-1].line)
    return roots


def parse_components(text: str) -> list[Component]:
    return build_components(parse_content_lines(text))
