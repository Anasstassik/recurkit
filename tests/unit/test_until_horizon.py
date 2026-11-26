from datetime import UTC, datetime

import pytest

from recurkit import RecurrenceSet, Rule
from recurkit.expand import Occurrence, after, before, between, occurrences

RULE = Rule.parse("FREQ=DAILY;UNTIL=20260105T090000", dtstart=datetime(2026, 1, 1, 9))
FIRST, LAST = datetime(2026, 1, 1, 9), datetime(2026, 1, 5, 9)
FAR = datetime(2027, 1, 1)
HORIZONS = [
    pytest.param(datetime(2026, 1, 3, 9), id="before-until"),
    pytest.param(LAST, id="at-until"),
    pytest.param(datetime(2026, 1, 10, 9), id="after-until"),
    pytest.param(datetime(2026, 1, 10, 9, tzinfo=UTC), id="after-until-utc"),
]


def _set_values(horizon: Occurrence) -> list[Occurrence]:
    end = horizon.replace(tzinfo=None) if isinstance(horizon, datetime) else horizon
    return list(RecurrenceSet(RULE).between(FIRST, end))


@pytest.mark.parametrize("horizon", HORIZONS)
def test_until_argument_is_a_horizon_for_occurrences_and_between(horizon: datetime) -> None:
    expected = _set_values(horizon)
    assert expected[-1] <= LAST
    assert list(occurrences(RULE, until=horizon)) == expected
    assert list(between(RULE, FIRST, FAR, until=horizon)) == expected
    assert list(between(RULE, datetime(2026, 1, 2), FAR, until=horizon)) == expected[1:]


@pytest.mark.parametrize("horizon", HORIZONS)
def test_until_argument_is_a_horizon_for_after_and_before(horizon: datetime) -> None:
    expected = _set_values(horizon)
    assert before(RULE, FAR, until=horizon) == expected[-1]
    assert after(RULE, expected[-1], until=horizon) is None
    assert after(RULE, FIRST, until=horizon) == expected[1]
    assert after(RULE, datetime(2026, 1, 6), until=horizon) is None
    assert RecurrenceSet(RULE).after(datetime(2026, 1, 6)) is None
    assert before(RULE, FAR) == RecurrenceSet(RULE).before(FAR) == LAST
