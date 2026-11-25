from datetime import UTC, date, datetime, timedelta

import pytest

from recurkit import Series, SeriesError, parse_ics
from recurkit.ical import Event, format_calendar
from recurkit.series import split


def _series(rule: str = "FREQ=WEEKLY;BYDAY=MO,WE", *extra: str) -> Series:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:x",
        "BEGIN:VEVENT",
        "UID:yoga",
        "SUMMARY:Yoga",
        "DTSTART;TZID=Europe/Kyiv:20260302T190000",
        "DURATION:PT1H",
        f"RRULE:{rule}",
        *extra,
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    (master,) = parse_ics("\n".join(lines))
    return Series.from_event(master)


def _at(month: int, day: int, hour: int = 17) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


def _starts(series: Series, high: datetime) -> list[datetime]:
    return [i.start for i in series.between(_at(1, 1), high)]


def test_ser_06_split_keeps_every_instance_across_a_dst_change() -> None:
    series = _series()
    head, tail = split(series, _at(4, 1, 16), uid="yoga-2")
    end = _at(6, 1)
    assert _starts(head, end) + _starts(tail, end) == _starts(series, end)
    assert head.uid == "yoga"
    assert tail.uid == "yoga-2"
    rule = head.master.recurrence
    assert rule is not None
    assert rule.rule.until == _at(3, 30, 16)
    assert tail.master.start == _at(4, 1, 16)


def test_ser_06_split_writes_until_in_utc_and_a_new_dtstart() -> None:
    head, tail = split(_series(), _at(3, 9), uid="yoga-2")
    text = format_calendar([head.master, tail.master])
    assert "RRULE:FREQ=WEEKLY;UNTIL=20260304T170000Z;BYDAY=MO,WE" in text
    assert "DTSTART;TZID=Europe/Kyiv:20260309T190000" in text
    assert "UID:yoga-2" in text


def test_ser_06_split_moves_dates_and_overrides_to_their_side() -> None:
    series = _series(
        "FREQ=WEEKLY;BYDAY=MO;UNTIL=20260330T170000Z",
        "EXDATE;TZID=Europe/Kyiv:20260309T190000,20260323T190000",
        "RDATE;TZID=Europe/Kyiv:20260305T190000,20260326T190000",
    )
    series.override(_at(3, 2), summary="First yoga")
    series.cancel(_at(3, 30, 16))
    head, tail = split(series, _at(3, 16), uid="yoga-2")
    assert _starts(head, _at(5, 1)) == [_at(3, 2), _at(3, 5)]
    assert _starts(tail, _at(5, 1)) == [_at(3, 16), _at(3, 26)]
    assert [i.summary for i in head.overrides] == ["First yoga"]
    assert [i.uid for i in tail.overrides] == ["yoga-2"]
    assert tail.master.exdates == frozenset({_at(3, 23)})
    rule = tail.master.recurrence
    assert rule is not None
    assert rule.rule.until == _at(3, 30, 17)


def test_ser_06_split_of_an_all_day_series_uses_a_date_until() -> None:
    master = Event(uid="duty", start=date(2026, 3, 2), length=timedelta(days=1))
    rule_event = parse_ics(
        "\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:x",
                "BEGIN:VEVENT",
                "UID:duty",
                "DTSTART;VALUE=DATE:20260302",
                "RRULE:FREQ=DAILY;INTERVAL=3",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )
    ).events[0]
    head, tail = split(Series(rule_event), date(2026, 3, 11), uid="duty-2")
    rule = head.master.recurrence
    assert rule is not None
    assert rule.rule.until == date(2026, 3, 8)
    assert [i.start for i in tail.between(date(2026, 3, 1), date(2026, 3, 18))] == [
        date(2026, 3, 11),
        date(2026, 3, 14),
        date(2026, 3, 17),
    ]
    with pytest.raises(SeriesError, match="no RRULE"):
        split(Series(master), date(2026, 3, 2), uid="duty-2")


def test_split_rejects_cuts_that_are_not_rule_instances() -> None:
    series = _series()
    with pytest.raises(SeriesError, match="not an instance") as caught:
        split(series, _at(3, 3), uid="yoga-2")
    assert caught.value.uid == "yoga"
    with pytest.raises(SeriesError, match="first instance"):
        split(series, _at(3, 2), uid="yoga-2")
    with pytest.raises(SeriesError, match="UID other than yoga"):
        split(series, _at(3, 4), uid="yoga")
    with pytest.raises(SeriesError, match="COUNT"):
        split(_series("FREQ=DAILY;COUNT=4"), _at(3, 3), uid="yoga-2")
