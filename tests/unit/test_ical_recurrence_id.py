from datetime import UTC, date, datetime

import pytest

from recurkit import ICalParseError, RuleValidationError, TimeZoneError, parse_ics
from recurkit.ical import Event

MASTER = [
    "BEGIN:VEVENT",
    "UID:standup",
    "SUMMARY:Stand-up",
    "DTSTART;TZID=Europe/Kyiv:20260105T090000",
    "DURATION:PT15M",
    "RRULE:FREQ=DAILY;COUNT=10",
    "END:VEVENT",
]


def _calendar(*blocks: list[str]) -> list[Event]:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:x"]
    for block in blocks:
        lines += block
    return list(parse_ics("\n".join([*lines, "END:VCALENDAR"])))


def _override(rid: str, *extra: str, uid: str = "standup") -> list[str]:
    return ["BEGIN:VEVENT", f"UID:{uid}", rid, *extra, "END:VEVENT"]


def test_rid_03_overrides_attach_to_their_master_by_uid_and_instant() -> None:
    moved = _override(
        "RECURRENCE-ID;TZID=Europe/Kyiv:20260107T090000",
        "DTSTART;TZID=Europe/Kyiv:20260107T113000",
        "SUMMARY:Stand-up (moved)",
    )
    cancelled = _override(
        "RECURRENCE-ID:20260108T070000Z", "DTSTART:20260108T070000Z", "STATUS:CANCELLED"
    )
    (master,) = _calendar(cancelled, MASTER, moved)
    assert not master.is_override
    assert [o.summary for o in master.overrides] == ["", "Stand-up (moved)"]
    third = datetime(2026, 1, 7, 7, tzinfo=UTC)
    found = master.override_for(third)
    assert found is not None
    assert found.summary == "Stand-up (moved)"
    assert found.start == datetime(2026, 1, 7, 9, 30, tzinfo=UTC)
    fourth = master.override_for(datetime(2026, 1, 8, 7, tzinfo=UTC))
    assert fourth is not None
    assert fourth.cancelled
    assert master.override_for(datetime(2026, 1, 9, 7, tzinfo=UTC)) is None


def test_rid_01_recurrence_id_has_the_value_type_of_the_master_dtstart() -> None:
    with pytest.raises(RuleValidationError, match=r"RID-01.*line 11.*UTC or zoned DATE-TIME"):
        _calendar(
            MASTER, _override("RECURRENCE-ID;VALUE=DATE:20260107", "DTSTART:20260107T120000Z")
        )
    with pytest.raises(RuleValidationError, match="RID-01"):
        _calendar(MASTER, _override("RECURRENCE-ID:20260107T090000", "DTSTART:20260107T090000"))
    all_day = [
        "BEGIN:VEVENT",
        "UID:d",
        "DTSTART;VALUE=DATE:20260105",
        "RRULE:FREQ=WEEKLY",
        "END:VEVENT",
    ]
    (master,) = _calendar(
        all_day, _override("RECURRENCE-ID;VALUE=DATE:20260112", "DTSTART:20260112T100000", uid="d")
    )
    assert master.overrides[0].recurrence_id == date(2026, 1, 12)
    assert master.overrides[0].start == datetime(2026, 1, 12, 10)


def test_rid_02_only_thisandfuture_range_is_accepted() -> None:
    (master,) = _calendar(
        MASTER,
        _override(
            "RECURRENCE-ID;RANGE=THISANDFUTURE;TZID=Europe/Kyiv:20260110T090000",
            "DTSTART;TZID=Europe/Kyiv:20260110T100000",
        ),
    )
    (split,) = master.overrides
    assert split.this_and_future
    assert split.is_override
    with pytest.raises(RuleValidationError, match=r"RID-02.*THISANDPRIOR"):
        _calendar(
            MASTER,
            _override(
                "RECURRENCE-ID;RANGE=THISANDPRIOR;TZID=Europe/Kyiv:20260110T090000",
                "DTSTART;TZID=Europe/Kyiv:20260110T100000",
            ),
        )


def test_override_without_master_stays_a_standalone_event() -> None:
    events = _calendar(
        _override("RECURRENCE-ID:20260107T070000Z", "DTSTART:20260107T080000Z", uid="lonely"),
        MASTER,
    )
    assert [(e.uid, e.is_override) for e in events] == [("lonely", True), ("standup", False)]
    assert events[1].overrides == ()
    with pytest.raises(TimeZoneError):
        _calendar(
            _override("RECURRENCE-ID;TZID=Nowhere/Zone:20260107T090000", "DTSTART:20260107T080000Z")
        )


def test_duplicate_masters_or_overrides_are_rejected() -> None:
    with pytest.raises(ICalParseError, match="line 11: two VEVENTs share UID standup"):
        _calendar(MASTER, MASTER)
    twice = _override("RECURRENCE-ID:20260107T070000Z", "DTSTART:20260107T080000Z")
    again = _override("RECURRENCE-ID;TZID=Europe/Kyiv:20260107T090000", "DTSTART:20260107T090000Z")
    with pytest.raises(ICalParseError, match="line 16: standup has two overrides"):
        _calendar(MASTER, twice, again)


def test_master_starts_are_unchanged_until_a_series_applies_overrides() -> None:
    moved = _override(
        "RECURRENCE-ID;TZID=Europe/Kyiv:20260107T090000", "DTSTART;TZID=Europe/Kyiv:20260107T113000"
    )
    (master,) = _calendar(MASTER, moved)
    starts = list(
        master.starts_between(datetime(2026, 1, 7, tzinfo=UTC), datetime(2026, 1, 8, tzinfo=UTC))
    )
    assert starts == [datetime(2026, 1, 7, 7, tzinfo=UTC)]
