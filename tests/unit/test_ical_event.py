from datetime import UTC, date, datetime, timedelta
from itertools import islice

import pytest

from recurkit import RuleValidationError, TimeZoneError
from recurkit.ical import Duration, Event, EventStatus, Transparency, parse_components, parse_event


def _event(*lines: str) -> Event:
    (component,) = parse_components("\n".join(["BEGIN:VEVENT", *lines, "END:VEVENT"]))
    return parse_event(component)


def _wall(value: object) -> datetime:
    assert isinstance(value, datetime)
    return value.replace(tzinfo=None)


@pytest.mark.parametrize(
    ("lines", "missing"),
    [(["DTSTART:20260105T090000"], "UID"), (["UID:a"], "DTSTART")],
)
def test_evt_01_uid_and_dtstart_are_required(lines: list[str], missing: str) -> None:
    with pytest.raises(RuleValidationError, match=f"EVT-01.*no {missing}"):
        _event(*lines)


def test_evt_02_dtend_and_duration_are_exclusive() -> None:
    with pytest.raises(RuleValidationError, match="EVT-02"):
        _event("UID:a", "DTSTART:20260105T090000", "DTEND:20260105T100000", "DURATION:PT1H")


@pytest.mark.parametrize(
    "end", ["DTEND:20260105T090000", "DTEND:20260105T080000", "DURATION:-PT1H"]
)
def test_evt_03_end_must_be_after_start(end: str) -> None:
    with pytest.raises(RuleValidationError, match="EVT-03"):
        _event("UID:a", "DTSTART:20260105T090000", end)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("DTSTART;VALUE=DATE:20260105", "DTEND:20260106T000000"),
        ("DTSTART:20260105T090000", "DTEND;VALUE=DATE:20260106"),
        ("DTSTART:20260105T090000", "DTEND:20260105T100000Z"),
        ("DTSTART:20260105T090000Z", "DTEND:20260105T100000"),
    ],
)
def test_evt_04_dtend_matches_dtstart_value_type(start: str, end: str) -> None:
    with pytest.raises(RuleValidationError, match="EVT-04"):
        _event("UID:a", start, end)


def test_evt_05_default_lengths_without_dtend_and_duration() -> None:
    all_day = _event("UID:a", "DTSTART;VALUE=DATE:20260228")
    assert all_day.all_day
    assert all_day.end == date(2026, 3, 1)
    moment = _event("UID:b", "DTSTART:20260105T090000Z")
    assert not moment.all_day
    assert moment.end == datetime(2026, 1, 5, 9, tzinfo=UTC)
    span = _event("UID:c", "DTSTART;VALUE=DATE:20260105", "DTEND;VALUE=DATE:20260108")
    assert span.length == timedelta(days=3)
    assert span.end_for(date(2026, 1, 30)) == date(2026, 2, 2)


def test_evt_06_all_day_duration_is_in_days_or_weeks() -> None:
    week = _event("UID:a", "DTSTART;VALUE=DATE:20260105", "DURATION:P1W")
    assert week.end == date(2026, 1, 12)
    with pytest.raises(RuleValidationError, match="EVT-06"):
        _event("UID:b", "DTSTART;VALUE=DATE:20260105", "DURATION:P1DT2H")


def test_evt_07_transp_and_status_values() -> None:
    plain = _event("UID:a", "DTSTART:20260105T090000")
    assert plain.transparency is Transparency.OPAQUE
    assert plain.status is None
    assert not plain.cancelled
    free = _event("UID:b", "DTSTART:20260105T090000", "TRANSP:transparent", "STATUS:CANCELLED")
    assert free.transparency is Transparency.TRANSPARENT
    assert free.status is EventStatus.CANCELLED
    assert free.cancelled
    with pytest.raises(RuleValidationError, match=r"EVT-07.*STATUS on line 4"):
        _event("UID:c", "DTSTART:20260105T090000", "STATUS:NEEDS-ACTION")
    with pytest.raises(RuleValidationError, match="EVT-07"):
        _event("UID:c", "DTSTART:20260105T090000", "TRANSP:BUSY")


def test_dur_02_nominal_day_keeps_wall_clock_across_dst() -> None:
    zone = "DTSTART;TZID=Europe/Kyiv:20260328T100000"
    nominal = _event("UID:a", zone, "DURATION:P1D")
    exact = _event("UID:b", zone, "DURATION:PT24H")
    assert nominal.length == Duration(days=1)
    assert _wall(nominal.end) == datetime(2026, 3, 29, 10)
    assert _wall(exact.end) == datetime(2026, 3, 29, 11)
    assert nominal.end.utcoffset() == timedelta(hours=3)  # type: ignore[union-attr]
    fixed = _event("UID:c", zone, "DTEND;TZID=Europe/Kyiv:20260328T113000")
    assert fixed.length == timedelta(minutes=90)
    later = fixed.end_for(datetime(2026, 3, 29, 9, tzinfo=UTC))
    assert _wall(later) == datetime(2026, 3, 29, 13, 30)


def test_dtend_in_another_zone_gives_exact_length() -> None:
    event = _event(
        "UID:a",
        "DTSTART;TZID=Europe/Kyiv:20260105T100000",
        "DTEND;TZID=America/New_York:20260105T040000",
    )
    assert event.length == timedelta(hours=1)
    assert event.tzid == "Europe/Kyiv"
    with pytest.raises(TimeZoneError):
        _event("UID:b", "DTSTART;TZID=Mars/Olympus:20260105T100000")


def test_event_instances_with_and_without_rrule() -> None:
    repeated = _event(
        "UID:a",
        "SUMMARY:Stand-up\\, daily",
        "DTSTART:20260105T090000",
        "DURATION:PT15M",
        "RRULE:FREQ=DAILY;COUNT=3",
        "EXDATE:20260106T090000",
        "RDATE:20260110T120000",
    )
    assert repeated.summary == "Stand-up, daily"
    assert repeated.recurrence is not None
    assert list(repeated.starts()) == [
        datetime(2026, 1, 5, 9),
        datetime(2026, 1, 7, 9),
        datetime(2026, 1, 10, 12),
    ]
    assert repeated.end_for(datetime(2026, 1, 10, 12)) == datetime(2026, 1, 10, 12, 15)
    single = _event(
        "UID:b",
        "DTSTART;TZID=Europe/Kyiv:20260105T090000",
        "RDATE;TZID=Europe/Kyiv:20260107T090000,20260105T090000",
        "RDATE:20260108T070000Z",
        "EXDATE:20260107T070000Z",
    )
    assert single.recurrence is None
    starts = list(islice(single.starts(), 5))
    assert [_wall(value) for value in starts] == [datetime(2026, 1, 5, 9), datetime(2026, 1, 8, 7)]


def test_starts_between_is_half_open_for_every_kind_of_event() -> None:
    daily = _event("UID:a", "DTSTART:20260105T090000", "RRULE:FREQ=DAILY")
    window = list(daily.starts_between(datetime(2026, 1, 6, 9), datetime(2026, 1, 8, 9)))
    assert window == [datetime(2026, 1, 6, 9), datetime(2026, 1, 7, 9)]
    days = _event("UID:b", "DTSTART;VALUE=DATE:20260105", "RDATE;VALUE=DATE:20260107,20260109")
    assert list(days.starts_between(date(2026, 1, 6), date(2026, 1, 9))) == [date(2026, 1, 7)]
    with pytest.raises(ValueError, match="before its start"):
        list(days.starts_between(date(2026, 1, 9), date(2026, 1, 6)))
