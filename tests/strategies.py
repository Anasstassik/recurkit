"""Hypothesis strategies shared by property and differential tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import strategies as st

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

dtstarts = st.builds(
    lambda days, minutes: datetime(2000, 1, 1) + timedelta(days=days, minutes=minutes),
    st.integers(0, 365 * 40),
    st.integers(0, 24 * 60 - 1),
)


def _int_list(values: st.SearchStrategy[int], max_size: int = 3) -> st.SearchStrategy[str]:
    return st.lists(values, min_size=1, max_size=max_size, unique=True).map(
        lambda items: ",".join(str(i) for i in items)
    )


month_days = st.one_of(st.integers(1, 31), st.integers(-31, -1))
plain_days = st.lists(st.sampled_from(WEEKDAY_CODES), min_size=1, max_size=4, unique=True).map(
    ",".join
)


def numeric_days(limit: int) -> st.SearchStrategy[str]:
    """Numeric BYDAY values only: dateutil intersects plain and numeric values instead of
    joining them, so mixed lists are kept out of the differential tests."""
    ordinals = st.one_of(st.integers(1, limit), st.integers(-limit, -1))
    item = st.tuples(ordinals, st.sampled_from(WEEKDAY_CODES)).map(lambda p: f"{p[0]}{p[1]}")
    return st.lists(item, min_size=1, max_size=3, unique=True).map(",".join)


@st.composite
def rule_texts(draw: st.DrawFn, freq: str, *, set_pos: bool = False, wkst: bool = False) -> str:
    """A valid RRULE text (without COUNT/UNTIL) for ``freq`` within the scope of RecurKit."""
    parts = [f"FREQ={freq}"]
    if draw(st.booleans()):
        parts.append(f"INTERVAL={draw(st.integers(1, 4))}")
    if draw(st.booleans()):
        parts.append("BYMONTH=" + draw(_int_list(st.integers(1, 12))))
    if freq != "WEEKLY" and draw(st.booleans()):
        parts.append("BYMONTHDAY=" + draw(_int_list(month_days)))
    if draw(st.booleans()):
        yearly_scope = freq == "YEARLY" and not any(p.startswith("BYMONTH=") for p in parts)
        if freq in ("MONTHLY", "YEARLY") and draw(st.booleans()):
            parts.append("BYDAY=" + draw(numeric_days(53 if yearly_scope else 5)))
        else:
            parts.append("BYDAY=" + draw(plain_days))
    if set_pos and len(parts) > 1 and any(p.startswith("BY") for p in parts):
        parts.append(
            "BYSETPOS=" + draw(_int_list(st.one_of(st.integers(1, 4), st.integers(-4, -1)), 2))
        )
    if wkst:
        parts.append("WKST=" + draw(st.sampled_from(WEEKDAY_CODES)))
    return ";".join(parts)
