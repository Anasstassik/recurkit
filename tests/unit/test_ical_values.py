from datetime import date, datetime, timedelta

import pytest

from recurkit import ICalParseError
from recurkit.ical import Duration, format_duration, parse_duration


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("P1W", Duration(weeks=1)),
        ("P15DT5H0M20S", Duration(days=15, seconds=5 * 3600 + 20)),
        ("PT1H30M", Duration(seconds=5400)),
        ("PT45S", Duration(seconds=45)),
        ("-PT15M", Duration(seconds=900, negative=True)),
        ("+P2D", Duration(days=2)),
        ("p1dt2h", Duration(days=1, seconds=7200)),
    ],
)
def test_dur_01_parse_valid_durations(text: str, expected: Duration) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text", ["", "P", "PT", "P1DT", "P1W2D", "PT1H20S", "PT5S1M", "1D", "P-1D", "P1.5D", "PT1H M"]
)
def test_dur_01_reject_malformed_durations(text: str) -> None:
    with pytest.raises(ICalParseError, match="DURATION"):
        parse_duration(text)


def test_duration_parse_error_carries_line_number() -> None:
    with pytest.raises(ICalParseError, match="line 12"):
        parse_duration("PXD", line=12)


@pytest.mark.parametrize(
    "text", ["P1W", "P15DT5H0M20S", "PT1H30M", "PT45S", "-PT15M", "P2D", "PT0S", "P1DT1H", "PT2M"]
)
def test_format_duration_round_trips(text: str) -> None:
    assert format_duration(parse_duration(text)) == text


def test_dur_02_days_are_nominal_and_time_is_exact() -> None:
    day = parse_duration("P1DT2H")
    assert day.nominal_days == 1
    assert day.exact == timedelta(hours=2)
    assert day.as_timedelta() == timedelta(days=1, hours=2)
    back = parse_duration("-P1W")
    assert back.nominal_days == -7
    assert back.exact == timedelta(0)
    start = datetime(2026, 3, 28, 10, 0)
    assert parse_duration("P1D").add_to_local(start) == datetime(2026, 3, 29, 10, 0)
    assert parse_duration("P1W").add_to_local(date(2026, 2, 26)) == date(2026, 3, 5)
    with pytest.raises(ValueError, match="whole days"):
        parse_duration("PT1H").add_to_local(date(2026, 1, 1))


def test_duration_rejects_inconsistent_parts() -> None:
    with pytest.raises(ValueError, match="negative"):
        Duration(days=-1)
    with pytest.raises(ValueError, match="weeks"):
        Duration(weeks=1, days=1)
    assert Duration(days=3).is_whole_days
    assert not Duration(seconds=1).is_whole_days


@pytest.mark.parametrize("text", ["PT\uff11H", "P\u0661D"])
def test_duration_accepts_only_ascii_digits(text: str) -> None:
    with pytest.raises(ICalParseError):
        parse_duration(text, 3)
