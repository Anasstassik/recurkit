from datetime import UTC, date, datetime, timedelta

import pytest

from recurkit import Series, SeriesError, parse_ics
from recurkit.ical import Event, EventStatus, Transparency, format_calendar

CALENDAR = "\n".join(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:x",
        "BEGIN:VEVENT",
        "UID:standup",
        "SUMMARY:Stand-up",
        "DTSTART;TZID=Europe/Kyiv:20260105T090000",
        "DURATION:PT15M",
        "RRULE:FREQ=DAILY;COUNT=5",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
)


def _series() -> Series:
    (master,) = parse_ics(CALENDAR)
    return Series.from_event(master)


def _at(day: int, hour: int = 7, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def test_ser_04_override_changes_only_one_instance() -> None:
    series = _series()
    moved = series.override(_at(7), start=_at(7, 9), summary="Stand-up (late)")
    assert moved.overridden
    assert moved.end == _at(7, 9, 15)
    items = list(series.instances())
    assert [i.summary for i in items].count("Stand-up (late)") == 1
    assert [i.start for i in items] == [_at(5), _at(6), _at(7, 9), _at(8), _at(9)]
    assert series.overrides == [moved]


def test_ser_04_cancel_hides_the_instance_and_keeps_it_on_request() -> None:
    series = _series()
    cancelled = series.cancel(_at(6))
    assert cancelled.cancelled
    assert _at(6) not in [i.start for i in series.instances()]
    assert len(list(series.instances(include_cancelled=True))) == 5
    again = series.override(_at(6), status=EventStatus.CONFIRMED)
    assert not again.cancelled
    assert len(series.overrides) == 1


def test_restore_drops_the_override() -> None:
    series = _series()
    series.override(_at(8), end=_at(8, 8), transparency=Transparency.TRANSPARENT)
    restored = series.restore(_at(8))
    assert restored is not None
    assert not restored.overridden
    assert restored.end == _at(8, 7, 15)
    assert series.overrides == []


def test_restore_of_an_added_instance_removes_it() -> None:
    master = Event(uid="trip", start=date(2026, 5, 18), length=timedelta(days=1))
    extra = Event(
        uid="trip",
        start=date(2026, 6, 1),
        length=timedelta(days=1),
        recurrence_id=date(2026, 6, 1),
    )
    series = Series(master, [extra])
    assert len(list(series.instances())) == 2
    assert series.restore(date(2026, 6, 1)) is None
    assert [i.start for i in series.instances()] == [date(2026, 5, 18)]


def test_ser_05_only_existing_instances_can_change() -> None:
    series = _series()
    with pytest.raises(SeriesError, match="not an instance of standup") as caught:
        series.cancel(_at(10))
    assert caught.value.uid == "standup"
    with pytest.raises(SeriesError, match="not an instance"):
        series.restore(_at(6, 8))
    with pytest.raises(SeriesError, match="before start"):
        series.override(_at(7), end=_at(7, 6))
    with pytest.raises(SeriesError, match="end"):
        series.override(_at(7), end=datetime(2026, 1, 7, 8))
    with pytest.raises(SeriesError, match="start"):
        series.override(_at(7), start=date(2026, 1, 7))


def test_ser_04_all_day_override_keeps_the_length_in_days() -> None:
    master = Event(uid="duty", start=date(2026, 3, 2), length=timedelta(days=2))
    series = Series(master)
    moved = series.override(date(2026, 3, 2), start=date(2026, 3, 3))
    assert moved.end == date(2026, 3, 5)
    assert moved.moved


def test_ser_04_overrides_survive_writing_and_reading_the_calendar() -> None:
    series = _series()
    series.override(_at(7), start=_at(7, 10), summary="Stand-up; late")
    series.cancel(_at(9))
    text = format_calendar(series.events())
    assert "RECURRENCE-ID;TZID=Europe/Kyiv:20260107T090000" in text
    (master,) = parse_ics(text)
    again = Series.from_event(master)
    assert list(again.instances(include_cancelled=True)) == list(
        series.instances(include_cancelled=True)
    )
