from datetime import date, datetime

import pytest

from recurkit import Rule
from recurkit.expand import plan_for
from recurkit.expand.expanders import expand_period
from recurkit.expand.periods import period_at
from recurkit.expand.setpos import apply_set_pos, resolve_position


def _period_with_set_pos(text: str, dtstart: datetime, step: int) -> list[date]:
    plan = plan_for(Rule.parse(text, dtstart=dtstart))
    period = period_at(plan, step)
    assert period is not None
    return apply_set_pos(expand_period(plan, period), plan.by_set_pos)


def test_rrule_22_last_work_day_of_month() -> None:
    text = "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1"
    start = datetime(2026, 1, 30, 17)
    assert _period_with_set_pos(text, start, 0) == [date(2026, 1, 30)]
    assert _period_with_set_pos(text, start, 4) == [date(2026, 5, 29)]
    third = "FREQ=MONTHLY;BYDAY=TU,WE,TH;BYSETPOS=3"
    assert _period_with_set_pos(third, datetime(1997, 9, 4, 9), 0) == [date(1997, 9, 4)]


def test_positions_outside_the_set_are_ignored() -> None:
    days = [date(2026, 1, d) for d in (5, 12, 19)]
    assert apply_set_pos(days, (4, -4)) == []
    assert apply_set_pos(days, (2, 7)) == [date(2026, 1, 12)]
    assert apply_set_pos([], (1, -1)) == []
    assert resolve_position(-3, 3) == 0
    assert resolve_position(366, 3) is None
    with pytest.raises(ValueError):
        resolve_position(0, 3)


def test_set_pos_result_is_sorted_without_duplicates() -> None:
    days = [date(2026, 1, d) for d in (5, 12, 19)]
    assert apply_set_pos(days, (-1, 1, -3)) == [date(2026, 1, 5), date(2026, 1, 19)]
    assert apply_set_pos(days, ()) == days
