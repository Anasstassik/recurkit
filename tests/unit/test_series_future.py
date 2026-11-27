from datetime import UTC, date, datetime, timedelta

from recurkit import Series, parse_ics
from recurkit.ical import EventStatus
from recurkit.series import load_series

KYIV = "Europe/Kyiv"


def _ics(*blocks: list[str]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:x"]
    for block in blocks:
        lines += ["BEGIN:VEVENT", "UID:sync", *block, "END:VEVENT"]
    return "\n".join([*lines, "END:VCALENDAR"])


MASTER = [
    "SUMMARY:Sync",
    f"DTSTART;TZID={KYIV}:20260319T100000",
    "DURATION:PT1H",
    "RRULE:FREQ=WEEKLY;COUNT=5",
]


def _future(rid: str, start: str, *extra: str) -> list[str]:
    return [
        f"RECURRENCE-ID;RANGE=THISANDFUTURE;TZID={KYIV}:{rid}",
        f"DTSTART;TZID={KYIV}:{start}",
        *extra,
    ]


def _series(*overrides: list[str]) -> Series:
    return load_series(parse_ics(_ics(MASTER, *overrides)))["sync"]


def _walls(series: Series, **kwargs: bool) -> list[tuple[str, str]]:
    return [(f"{item.start:%m-%d %H:%M}", item.summary) for item in series.instances(**kwargs)]


def test_ser_08_thisandfuture_moves_every_later_instance_by_the_same_wall_time() -> None:
    series = _series(
        _future("20260326T100000", "20260326T113000", "SUMMARY:Sync v2", "DURATION:PT30M")
    )
    assert _walls(series) == [
        ("03-19 10:00", "Sync"),
        ("03-26 11:30", "Sync v2"),
        ("04-02 11:30", "Sync v2"),
        ("04-09 11:30", "Sync v2"),
        ("04-16 11:30", "Sync v2"),
    ]
    first, second = list(series.instances())[1:3]
    assert first.start.utcoffset() == timedelta(hours=2)
    assert second.start.utcoffset() == timedelta(hours=3)
    assert second.end - second.start == timedelta(minutes=30)
    assert second.recurrence_id == datetime(2026, 4, 2, 7, tzinfo=UTC)
    assert second.overridden and second.moved


def test_ser_08_single_override_and_a_later_range_both_apply() -> None:
    series = _series(
        _future("20260402T100000", "20260402T090000", "SUMMARY:Early"),
        [f"RECURRENCE-ID;TZID={KYIV}:20260409T100000", f"DTSTART;TZID={KYIV}:20260410T100000"],
        _future("20260416T100000", "20260416T100000", "SUMMARY:Back"),
    )
    assert _walls(series) == [
        ("03-19 10:00", "Sync"),
        ("03-26 10:00", "Sync"),
        ("04-02 09:00", "Early"),
        ("04-10 10:00", ""),
        ("04-16 10:00", "Back"),
    ]
    found = series.instance(datetime(2026, 4, 2, 7, tzinfo=UTC))
    assert found is not None and found.summary == "Early"


def test_thisandfuture_cancel_ends_the_series_but_keeps_the_instances_on_request() -> None:
    series = _series(_future("20260402T100000", "20260402T100000", "STATUS:CANCELLED"))
    assert len(list(series.instances())) == 2
    cancelled = list(series.instances(include_cancelled=True))[2:]
    assert [item.status for item in cancelled] == [EventStatus.CANCELLED] * 3


def test_window_finds_an_instance_moved_into_it_from_outside() -> None:
    series = _series(_future("20260326T100000", "20260327T100000"))
    low = datetime(2026, 4, 3, tzinfo=UTC)
    window = list(series.between(low, low + timedelta(days=1)))
    assert [item.recurrence_id for item in window] == [datetime(2026, 4, 2, 7, tzinfo=UTC)]
    before = list(series.between(low - timedelta(days=1), low))
    assert before == []


def test_all_day_range_moves_by_days_and_is_written_back() -> None:
    text = _ics(
        ["DTSTART;VALUE=DATE:20260105", "RRULE:FREQ=WEEKLY;COUNT=3"],
        ["RECURRENCE-ID;RANGE=THISANDFUTURE;VALUE=DATE:20260112", "DTSTART;VALUE=DATE:20260114"],
    )
    series = load_series(parse_ics(text))["sync"]
    starts = [item.start for item in series.instances()]
    assert starts == [date(2026, 1, 5), date(2026, 1, 14), date(2026, 1, 21)]
    assert [event.this_and_future for event in series.events()] == [False, True]


def test_load_series_keys_masters_by_uid_and_skips_lonely_overrides() -> None:
    lonely = (
        "BEGIN:VEVENT\nUID:other\nRECURRENCE-ID:20260107T070000Z\n"
        "DTSTART:20260107T080000Z\nEND:VEVENT\n"
    )
    text = _ics(MASTER).replace("END:VCALENDAR", lonely + "END:VCALENDAR")
    loaded = load_series(parse_ics(text))
    assert list(loaded) == ["sync"]
    assert loaded["sync"].uid == "sync"
