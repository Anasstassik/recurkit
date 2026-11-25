from datetime import datetime, timedelta
from itertools import islice

from hypothesis import given
from hypothesis import strategies as st

from recurkit.ical import format_recurrence, parse_recurrence

ZONES = ("Europe/Kyiv", "America/New_York", "Asia/Kolkata")
RULES = (
    "FREQ=DAILY;COUNT=12",
    "FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=9",
    "FREQ=MONTHLY;BYMONTHDAY=1,15,-1;COUNT=8",
    "FREQ=DAILY;INTERVAL=3",
)
starts = st.builds(
    lambda days, minutes: datetime(2026, 1, 1) + timedelta(days=days, minutes=minutes),
    st.integers(0, 600),
    st.integers(0, 24 * 60 - 1),
)


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S")


@st.composite
def explicit_line(draw: st.DrawFn, name: str, kind: str, start: datetime) -> str:
    value = start + timedelta(days=draw(st.integers(-5, 60)), minutes=draw(st.integers(0, 600)))
    forms = {"floating": ["floating"], "utc": ["utc", "zone"], "zoned": ["own", "utc", "zone"]}
    form = draw(st.sampled_from(forms[kind]))
    if form == "utc":
        return f"{name}:{_stamp(value)}Z"
    if form == "zone":
        return f"{name};TZID={draw(st.sampled_from(ZONES[1:]))}:{_stamp(value)}"
    if form == "own":
        return f"{name};TZID={ZONES[0]}:{_stamp(value)}"
    return f"{name}:{_stamp(value)}"


@st.composite
def recurrence_texts(draw: st.DrawFn) -> str:
    kind = draw(st.sampled_from(("floating", "utc", "zoned")))
    start = draw(starts)
    dtstart = {
        "floating": f"DTSTART:{_stamp(start)}",
        "utc": f"DTSTART:{_stamp(start)}Z",
        "zoned": f"DTSTART;TZID={ZONES[0]}:{_stamp(start)}",
    }[kind]
    lines = [dtstart, f"RRULE:{draw(st.sampled_from(RULES))}"]
    for name in ("RDATE", "EXDATE"):
        lines += draw(st.lists(explicit_line(name, kind, start), max_size=4))
    return "\r\n".join(lines)


@given(recurrence_texts())
def test_written_recurrence_reads_back_as_the_same_set(text: str) -> None:
    rset = parse_recurrence(text)
    again = parse_recurrence(format_recurrence(rset))
    assert list(islice(again, 40)) == list(islice(rset, 40))
    assert again.rdates == rset.rdates
    assert again.exdates == rset.exdates
