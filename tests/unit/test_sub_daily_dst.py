from datetime import UTC, datetime, timedelta
from itertools import pairwise

from recurkit import RecurrenceSet, Rule

BERLIN = "Europe/Berlin"


def _walls(text: str, dtstart: datetime) -> list[tuple[str, timedelta | None]]:
    rset = RecurrenceSet(Rule.parse(text, dtstart=dtstart, tzid=BERLIN))
    values = list(rset)
    assert all(a < b for a, b in pairwise(values))  # type: ignore[operator]
    return [(v.strftime("%d %H:%M"), v.utcoffset()) for v in values]  # type: ignore[union-attr]


SUMMER, WINTER = timedelta(hours=2), timedelta(hours=1)


def test_tz_02_dtstart_in_gap_is_not_followed_by_earlier_instances() -> None:
    assert _walls("FREQ=MINUTELY;INTERVAL=15;COUNT=4", datetime(2026, 3, 29, 2, 30)) == [
        ("29 03:30", SUMMER),
        ("29 03:45", SUMMER),
        ("29 04:00", SUMMER),
        ("29 04:15", SUMMER),
    ]


def test_tz_02_shifted_dtstart_is_not_repeated_by_the_rule() -> None:
    assert _walls("FREQ=HOURLY;COUNT=3", datetime(2026, 3, 29, 2, 30)) == [
        ("29 03:30", SUMMER),
        ("29 04:30", SUMMER),
        ("29 05:30", SUMMER),
    ]
    assert _walls("FREQ=DAILY;BYHOUR=2,3;BYMINUTE=30;COUNT=3", datetime(2026, 3, 29, 2, 30)) == [
        ("29 03:30", SUMMER),
        ("30 02:30", SUMMER),
        ("30 03:30", SUMMER),
    ]


def test_tz_01_utc_until_in_the_second_pass_of_a_fold_keeps_the_first_pass() -> None:
    until = datetime(2026, 10, 25, 1, 30, tzinfo=UTC).strftime("%Y%m%dT%H%M%SZ")
    assert _walls(f"FREQ=MINUTELY;INTERVAL=20;UNTIL={until}", datetime(2026, 10, 25, 1, 40)) == [
        ("25 01:40", SUMMER),
        ("25 02:00", SUMMER),
        ("25 02:20", SUMMER),
        ("25 02:40", SUMMER),
    ]
    assert _walls("FREQ=HOURLY;UNTIL=20261025T020000Z", datetime(2026, 10, 25, 1, 0)) == [
        ("25 01:00", SUMMER),
        ("25 02:00", SUMMER),
        ("25 03:00", WINTER),
    ]
