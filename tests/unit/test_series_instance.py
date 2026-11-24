from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from recurkit.ical import Event, EventStatus, Transparency
from recurkit.series import Instance
from recurkit.series.instance import same_kind, sort_key

KYIV = timezone(timedelta(hours=2))


def test_sort_key_puts_dates_and_zoned_values_on_one_axis() -> None:
    assert sort_key(date(2026, 3, 1)) == datetime(2026, 3, 1)
    assert sort_key(datetime(2026, 3, 1, 9)) == datetime(2026, 3, 1, 9)
    assert sort_key(datetime(2026, 3, 1, 9, tzinfo=KYIV)) == datetime(2026, 3, 1, 7)


def test_same_kind_separates_dates_floating_and_zoned_values() -> None:
    day = date(2026, 3, 1)
    floating = datetime(2026, 3, 1, 9)
    zoned = datetime(2026, 3, 1, 9, tzinfo=UTC)
    assert same_kind(day, day)
    assert not same_kind(floating, day)
    assert not same_kind(day, floating)
    assert same_kind(floating, floating)
    assert not same_kind(zoned, floating)
    assert same_kind(datetime(2026, 3, 2, tzinfo=KYIV), zoned)


def test_instance_of_master_copies_the_master_fields() -> None:
    master = Event(
        uid="gym",
        start=datetime(2026, 3, 2, 18, tzinfo=UTC),
        length=timedelta(hours=1),
        summary="Gym",
        transparency=Transparency.TRANSPARENT,
    )
    start = datetime(2026, 3, 4, 18, tzinfo=UTC)
    item = Instance.of_master(master, start)
    assert item.recurrence_id == start
    assert item.end == start + timedelta(hours=1)
    assert item.summary == "Gym"
    assert not item.overridden
    assert not item.moved
    assert not item.busy


def test_ser_01_instance_of_override_takes_its_own_fields() -> None:
    rid = datetime(2026, 3, 4, 18, tzinfo=UTC)
    override = Event(
        uid="gym",
        start=rid + timedelta(hours=1),
        length=timedelta(minutes=30),
        summary="Gym (short)",
        recurrence_id=rid,
    )
    item = Instance.of_override(override)
    assert item.overridden
    assert item.moved
    assert item.busy
    assert item.end == rid + timedelta(hours=1, minutes=30)
    assert item.key == (sort_key(item.start), sort_key(rid))


def test_ser_02_cancelled_instance_is_not_busy() -> None:
    rid = date(2026, 3, 4)
    override = Event(
        uid="gym",
        start=rid,
        length=timedelta(days=1),
        status=EventStatus.CANCELLED,
        recurrence_id=rid,
    )
    item = Instance.of_override(override)
    assert item.cancelled
    assert not item.busy


def test_instance_of_override_needs_a_recurrence_id() -> None:
    plain = Event(uid="gym", start=date(2026, 3, 4), length=timedelta(days=1), line=7)
    with pytest.raises(ValueError, match="line 7"):
        Instance.of_override(plain)
