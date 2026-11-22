from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from recurkit.calendar_math import Weekday
from recurkit.rule.model import Frequency, Rule, WeekdayNum

WEEKDAY_NAMES = {
    Weekday.MO: "Monday",
    Weekday.TU: "Tuesday",
    Weekday.WE: "Wednesday",
    Weekday.TH: "Thursday",
    Weekday.FR: "Friday",
    Weekday.SA: "Saturday",
    Weekday.SU: "Sunday",
}
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
UNITS = {
    Frequency.DAILY: ("daily", "day"),
    Frequency.WEEKLY: ("weekly", "week"),
    Frequency.MONTHLY: ("monthly", "month"),
    Frequency.YEARLY: ("yearly", "year"),
}
WORKDAYS = frozenset({Weekday.MO, Weekday.TU, Weekday.WE, Weekday.TH, Weekday.FR})
SPECIAL_ORDINALS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}


def ordinal(n: int) -> str:
    if n == -1:
        return "last"
    if n < 0:
        return f"{ordinal(-n)} to last"
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _position(n: int) -> str:
    if n == -1:
        return "last"
    return SPECIAL_ORDINALS.get(n, ordinal(n))


def join_words(words: Sequence[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _weekday_item(item: WeekdayNum) -> str:
    name = WEEKDAY_NAMES[item.weekday]
    return name if item.n is None else f"the {_position(item.n)} {name}"


def _days(rule: Rule) -> tuple[str | None, bool]:
    if not rule.by_day:
        return None, False
    weekdays = {item.weekday for item in rule.by_day}
    plain = not rule.has_numeric_by_day
    if plain and len(rule.by_set_pos) == 1 and weekdays in (WORKDAYS, set(Weekday)):
        kind = "weekday" if weekdays == WORKDAYS else "day"
        return f"the {_position(rule.by_set_pos[0])} {kind}", True
    if plain and weekdays == WORKDAYS:
        return "weekdays", False
    if plain and len(weekdays) == 7:
        return "every day of the week", False
    return join_words([_weekday_item(item) for item in rule.by_day]), False


def _period_phrase(rule: Rule) -> str:
    adverb, unit = UNITS[rule.freq]
    if rule.interval == 1:
        return adverb
    if rule.interval == 2:
        return f"every other {unit}"
    return f"every {rule.interval} {unit}s"


def _limits(rule: Rule) -> list[str]:
    parts: list[str] = []
    if rule.by_week_no:
        label = "week" if len(rule.by_week_no) == 1 else "weeks"
        if any(n < 0 for n in rule.by_week_no):
            weeks = join_words([ordinal(n) for n in rule.by_week_no])
            parts.append(f"in the {weeks} {label} of the year")
        else:
            parts.append(f"in {label} " + join_words([str(n) for n in rule.by_week_no]))
    if rule.by_month:
        parts.append("in " + join_words([MONTH_NAMES[m - 1] for m in rule.by_month]))
    if rule.by_year_day:
        days = join_words([ordinal(n) for n in rule.by_year_day])
        parts.append(f"on the {days} day of the year")
    if rule.by_month_day:
        days = join_words([ordinal(n) for n in rule.by_month_day])
        if any(n < 0 for n in rule.by_month_day):
            unit = "day" if len(rule.by_month_day) == 1 else "days"
            days += f" {unit} of the month"
        parts.append(f"on the {days}")
    weekdays, uses_set_pos = _days(rule)
    if weekdays is not None:
        parts.append(f"on {weekdays}")
    if rule.by_set_pos and not uses_set_pos:
        parts.append("keeping the " + join_words([ordinal(n) for n in rule.by_set_pos]))
    return parts


def _format_date(value: date | datetime) -> str:
    text = f"{value.day} {MONTH_NAMES[value.month - 1]} {value.year}"
    if isinstance(value, datetime):
        text += f" {value:%H:%M}" + (" UTC" if value.tzinfo is not None else "")
    return text


def describe(rule: Rule) -> str:
    parts = [_period_phrase(rule), *_limits(rule)]
    if isinstance(rule.dtstart, datetime):
        parts.append(f"at {rule.dtstart:%H:%M}")
    if rule.wkst is not Weekday.MO and (rule.freq is Frequency.WEEKLY or rule.by_week_no):
        parts.append(f"with weeks starting on {WEEKDAY_NAMES[rule.wkst]}")
    text = " ".join(parts)
    if rule.count is not None:
        text += ", once" if rule.count == 1 else f", {rule.count} times"
    elif rule.until is not None:
        text += f", until {_format_date(rule.until)}"
    return text
