from datetime import UTC, date, datetime, timedelta

import pytest

from recurkit import Series, SeriesError, parse_ics
from recurkit.ical import Event

MASTER = [
    "BEGIN:VEVENT",
    "UID:standup",
    "SUMMARY:Stand-up",
    "DTSTART:20260105T090000Z",
    "DURATION:PT15M",
    "RRULE:FREQ=DAILY;COUNT=5",
    "END:VEVENT",
]


def _series(*blocks: list[str]) -> Series:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:x", *MASTER]
    for block in blocks:
        lines += block
    (master,) = parse_ics("\n".join([*lines, "END:VCALENDAR"]))
    return Series.from_event(master)


def _override(rid: str, *extra: str) -> list[str]:
    return ["BEGIN:VEVENT", "UID:standup", f"RECURRENCE-ID:{rid}", *extra, "END:VEVENT"]


def _at(day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def test_series_without_overrides_lists_the_master_instances() -> None:
    series = _series()
    assert series.uid == "standup"
    assert repr(series) == "Series('standup', overrides=0)"
    assert [i.start for i in series.instances()] == [_at(d) for d in range(5, 10)]
    assert all(i.end - i.start == timedelta(minutes=15) for i in series.instances())


def test_ser_01_override_replaces_the_instance_with_its_recurrence_id() -> None:
    series = _series(_override("20260107T090000Z", "DTSTART:20260107T090000Z", "SUMMARY:Planning"))
    summaries = [i.summary for i in series.instances()]
    assert summaries == ["Stand-up", "Stand-up", "Planning", "Stand-up", "Stand-up"]
    third = series.instance(_at(7))
    assert third is not None
    assert third.overridden
    assert len(series.overrides) == 1


def test_ser_02_cancelled_instances_are_skipped_unless_asked() -> None:
    series = _series(_override("20260106T090000Z", "DTSTART:20260106T090000Z", "STATUS:CANCELLED"))
    assert _at(6) not in [i.start for i in series.instances()]
    every = list(series.instances(include_cancelled=True))
    assert len(every) == 5
    assert [i.cancelled for i in every] == [False, True, False, False, False]


def test_ser_03_moved_instance_counts_in_the_window_of_its_new_start() -> None:
    series = _series(
        _override("20260106T090000Z", "DTSTART:20260110T120000Z"),
        _override("20260108T090000Z", "DTSTART:20260108T070000Z"),
    )
    starts = [i.start for i in series.instances()]
    assert starts == [_at(5), _at(7), _at(8, 7), _at(9), _at(10, 12)]
    first_days = [i.start for i in series.between(_at(5), _at(7))]
    assert first_days == [_at(5)]
    weekend = [i.recurrence_id for i in series.between(_at(10), _at(11))]
    assert weekend == [_at(6)]


def test_instance_lookup_by_recurrence_id() -> None:
    series = _series()
    found = series.instance(_at(8))
    assert found is not None
    assert not found.overridden
    assert series.instance(_at(8, 10)) is None
    assert series.instance(_at(12)) is None
    assert not series.is_instance(datetime(2026, 1, 8, 9))
    assert not series.is_instance(date(2026, 1, 8))


def test_master_without_rule_has_one_instance_plus_rdates() -> None:
    master = Event(
        uid="trip",
        start=date(2026, 5, 18),
        length=timedelta(days=2),
        rdates=(date(2026, 6, 1),),
    )
    series = Series(master)
    assert [i.start for i in series.instances()] == [date(2026, 5, 18), date(2026, 6, 1)]
    assert series.is_instance(date(2026, 6, 1))
    assert not series.is_instance(date(2026, 6, 2))


def test_series_rejects_overrides_that_do_not_fit_the_master() -> None:
    master = Event(uid="trip", start=date(2026, 5, 18), length=timedelta(days=1))
    other = Event(uid="other", start=date(2026, 5, 18), length=timedelta(days=1))
    with pytest.raises(SeriesError, match="cannot change trip"):
        Series(
            master,
            [
                Event(
                    uid="other",
                    start=date(2026, 5, 19),
                    length=timedelta(days=1),
                    recurrence_id=date(2026, 5, 18),
                )
            ],
        )
    with pytest.raises(SeriesError, match="start"):
        Series(
            master,
            [
                Event(
                    uid="trip",
                    start=_at(19),
                    length=timedelta(hours=1),
                    recurrence_id=date(2026, 5, 18),
                )
            ],
        )
    with pytest.raises(SeriesError, match="override, not a master"):
        Series(_as_override(other))


def _as_override(event: Event) -> Event:
    return Event(
        uid=event.uid, start=event.start, length=event.length, recurrence_id=event.start, line=4
    )
