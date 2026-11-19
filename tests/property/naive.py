"""A deliberately naive, independent definition of "day d belongs to the rule".

It does not use recurkit.expand: everything is computed by brute force over
calendar days, so a bug in the generator cannot hide in a shared helper.
Only rules without BYSETPOS are covered (BYSETPOS needs the whole period).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from recurkit import Frequency, Rule


def _days_of_month(day: date) -> list[date]:
    first = day.replace(day=1)
    result = []
    current = first
    while current.month == first.month:
        result.append(current)
        current += timedelta(days=1)
    return result


def _days_of_year(day: date) -> list[date]:
    current, result = date(day.year, 1, 1), []
    while current.year == day.year:
        result.append(current)
        current += timedelta(days=1)
    return result


def _start(rule: Rule) -> date:
    dtstart = rule.require_dtstart()
    return dtstart.date() if isinstance(dtstart, datetime) else dtstart


def matches(rule: Rule, day: date) -> bool:
    """True if ``day`` satisfies every BYxxx part (with DTSTART defaults), ignoring INTERVAL."""
    start = _start(rule)
    if rule.by_month and day.month not in rule.by_month:
        return False
    by_month_day = rule.by_month_day
    by_day = rule.by_day
    if rule.freq is Frequency.WEEKLY and not by_day:
        return day.weekday() == start.weekday()
    if rule.freq is Frequency.MONTHLY and not by_day and not by_month_day:
        by_month_day = (start.day,)
    if rule.freq is Frequency.YEARLY and not by_day and not by_month_day:
        if not rule.by_month and day.month != start.month:
            return False
        by_month_day = (start.day,)
    if by_month_day:
        length = len(_days_of_month(day))
        if not any(day.day == v or day.day == length + v + 1 for v in by_month_day):
            return False
    if by_day:
        in_year = rule.freq is Frequency.YEARLY and not rule.by_month
        scope = _days_of_year(day) if in_year else _days_of_month(day)
        same = [d for d in scope if d.weekday() == day.weekday()]
        position = same.index(day)
        ok = False
        for item in by_day:
            if item.weekday.value != day.weekday():
                continue
            if item.n is None or item.n == position + 1 or item.n == position - len(same):
                ok = True
        if not ok:
            return False
    return True


def aligned_with_interval(rule: Rule, day: date) -> bool:
    """True if ``day`` lies in a period that INTERVAL selects, counted from DTSTART."""
    start, k = _start(rule), rule.interval
    if rule.freq is Frequency.DAILY:
        return (day - start).days % k == 0
    if rule.freq is Frequency.MONTHLY:
        return ((day.year * 12 + day.month) - (start.year * 12 + start.month)) % k == 0
    if rule.freq is Frequency.YEARLY:
        return (day.year - start.year) % k == 0

    def week_start(d: date) -> date:
        while d.weekday() != rule.wkst.value:
            d -= timedelta(days=1)
        return d

    return ((week_start(day) - week_start(start)).days // 7) % k == 0


def each_day(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
