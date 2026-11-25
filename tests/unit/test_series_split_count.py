from datetime import UTC, datetime

from recurkit import Series, parse_ics
from recurkit.ical import format_calendar
from recurkit.series import split


def _series(rule: str, *extra: str) -> Series:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:x",
        "BEGIN:VEVENT",
        "UID:course",
        "SUMMARY:Course",
        "DTSTART:20260302T170000Z",
        "DURATION:PT90M",
        f"RRULE:{rule}",
        *extra,
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    (master,) = parse_ics("\n".join(lines))
    return Series.from_event(master)


def _at(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 17, tzinfo=UTC)


def _starts(series: Series) -> list[datetime]:
    return [i.start for i in series.instances()]


def test_ser_07_count_is_shared_between_the_two_parts() -> None:
    series = _series("FREQ=WEEKLY;BYDAY=MO,TH;COUNT=6")
    head, tail = split(series, _at(3, 12), uid="course-2")
    assert _starts(head) + _starts(tail) == _starts(series)
    head_rule, tail_rule = head.master.recurrence, tail.master.recurrence
    assert head_rule is not None
    assert tail_rule is not None
    assert (head_rule.rule.count, tail_rule.rule.count) == (3, 3)
    assert head_rule.rule.until is None


def test_ser_07_excluded_instances_still_count() -> None:
    series = _series("FREQ=DAILY;COUNT=5", "EXDATE:20260303T170000Z")
    head, tail = split(series, _at(3, 5), uid="course-2")
    assert _starts(head) == [_at(3, 2), _at(3, 4)]
    assert _starts(tail) == [_at(3, 5), _at(3, 6)]
    text = format_calendar([head.master, tail.master])
    assert "RRULE:FREQ=DAILY;COUNT=3" in text
    assert "RRULE:FREQ=DAILY;COUNT=2" in text


def test_ser_07_split_at_the_last_counted_instance() -> None:
    series = _series("FREQ=MONTHLY;COUNT=3")
    head, tail = split(series, _at(5, 2), uid="course-2")
    assert _starts(head) == [_at(3, 2), _at(4, 2)]
    assert _starts(tail) == [_at(5, 2)]
