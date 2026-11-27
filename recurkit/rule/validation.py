from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import fields
from datetime import datetime

from recurkit.errors import RuleValidationError
from recurkit.rule.model import Frequency, Rule, RuleParts

MAX_MONTH_DAY = 31
MAX_SET_POS = 366
MAX_YEAR_DAY = 366
MAX_WEEK_ORDINAL = 53

type _Check = Callable[[RuleParts], Iterator[RuleValidationError]]


def _signed_range_errors(
    requirement_id: str, part: str, values: tuple[int, ...], limit: int
) -> Iterator[RuleValidationError]:
    for value in values:
        if value == 0 or not -limit <= value <= limit:
            yield RuleValidationError(
                requirement_id, f"{part} value {value} must be in 1..{limit} or -{limit}..-1"
            )


def _is_utc(value: datetime) -> bool:
    offset = value.utcoffset()
    return offset is not None and not offset


def _check_dtstart(rule: RuleParts) -> Iterator[RuleValidationError]:
    dtstart = rule.dtstart
    if rule.tzid is not None and not rule.tzid.strip():
        yield RuleValidationError("TZ-04", "TZID must not be empty")
    if isinstance(dtstart, datetime) and dtstart.tzinfo is not None:
        if not _is_utc(dtstart):
            yield RuleValidationError(
                "DT-03", "DTSTART with a UTC offset is not allowed: use UTC or a TZID"
            )
        elif rule.tzid is not None:
            yield RuleValidationError("DT-02", "TZID must not be applied to a UTC DTSTART")
    elif dtstart is not None and not isinstance(dtstart, datetime) and rule.tzid is not None:
        yield RuleValidationError("DT-04", "TZID must not be applied to a DATE value")


def _check_interval(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.interval < 1:
        yield RuleValidationError("RRULE-05", f"INTERVAL must be positive, got {rule.interval}")


def _check_ranges(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.count is not None and rule.count < 1:
        yield RuleValidationError("RRULE-06", f"COUNT must be positive, got {rule.count}")
    for month in rule.by_month:
        if not 1 <= month <= 12:
            yield RuleValidationError("RRULE-06", f"BYMONTH value {month} must be in 1..12")
    yield from _signed_range_errors("RRULE-06", "BYMONTHDAY", rule.by_month_day, MAX_MONTH_DAY)
    yield from _signed_range_errors("RRULE-06", "BYYEARDAY", rule.by_year_day, MAX_YEAR_DAY)
    yield from _signed_range_errors("RRULE-06", "BYWEEKNO", rule.by_week_no, MAX_WEEK_ORDINAL)
    yield from _signed_range_errors("RRULE-06", "BYSETPOS", rule.by_set_pos, MAX_SET_POS)
    ordinals = tuple(item.n for item in rule.by_day if item.n is not None)
    yield from _signed_range_errors("RRULE-06", "BYDAY ordinal", ordinals, MAX_WEEK_ORDINAL)


def _check_count_until(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.count is not None and rule.until is not None:
        yield RuleValidationError("RRULE-07", "UNTIL and COUNT must not occur in the same rule")


def _check_until_type(rule: RuleParts) -> Iterator[RuleValidationError]:
    until, dtstart = rule.until, rule.dtstart
    if until is None or dtstart is None:
        return
    if isinstance(until, datetime) != isinstance(dtstart, datetime):
        kind = "DATE-TIME" if isinstance(dtstart, datetime) else "DATE"
        yield RuleValidationError("RRULE-08", f"UNTIL must be a {kind} value like DTSTART")
        return
    if not isinstance(until, datetime) or not isinstance(dtstart, datetime):
        return
    zoned = rule.tzid is not None or dtstart.tzinfo is not None
    if zoned and not _is_utc(until):
        yield RuleValidationError(
            "RRULE-10", "UNTIL must be in UTC when DTSTART is in UTC or has a TZID"
        )
    elif not zoned and until.tzinfo is not None:
        yield RuleValidationError(
            "RRULE-09", "UNTIL must be a local (floating) time when DTSTART is floating"
        )


def _check_by_day(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.has_numeric_by_day and rule.freq not in (Frequency.MONTHLY, Frequency.YEARLY):
        yield RuleValidationError(
            "RRULE-13",
            f"BYDAY with a numeric value is only allowed for MONTHLY or YEARLY, not {rule.freq}",
        )


def _check_by_month_day(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.by_month_day and rule.freq is Frequency.WEEKLY:
        yield RuleValidationError("RRULE-14", "BYMONTHDAY must not be used with FREQ=WEEKLY")


def _check_by_year_day(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.by_year_day and rule.freq in (Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY):
        yield RuleValidationError("RRULE-23", f"BYYEARDAY must not be used with FREQ={rule.freq}")


def _check_by_week_no(rule: RuleParts) -> Iterator[RuleValidationError]:
    if not rule.by_week_no:
        return
    if rule.freq is not Frequency.YEARLY:
        yield RuleValidationError("RRULE-24", "BYWEEKNO may only be used with FREQ=YEARLY")
    elif rule.has_numeric_by_day:
        yield RuleValidationError(
            "RRULE-25", "BYDAY must not have a numeric value in a YEARLY rule with BYWEEKNO"
        )


def _check_by_set_pos(rule: RuleParts) -> Iterator[RuleValidationError]:
    if rule.by_set_pos and not rule.has_by_parts:
        yield RuleValidationError(
            "RRULE-15", "BYSETPOS must be used together with another BYxxx rule part"
        )


_CHECKS: tuple[_Check, ...] = (
    _check_dtstart,
    _check_interval,
    _check_ranges,
    _check_count_until,
    _check_until_type,
    _check_by_day,
    _check_by_month_day,
    _check_by_year_day,
    _check_by_week_no,
    _check_by_set_pos,
)


def find_violations(rule: RuleParts) -> list[RuleValidationError]:
    return [error for check in _CHECKS for error in check(rule)]


def validate(parts: RuleParts) -> Rule:
    if isinstance(parts, Rule):
        return parts
    return Rule(**{field.name: getattr(parts, field.name) for field in fields(RuleParts)})
