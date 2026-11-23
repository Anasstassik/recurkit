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
    ordinals = st.one_of(st.integers(1, limit), st.integers(-limit, -1))
    item = st.tuples(ordinals, st.sampled_from(WEEKDAY_CODES)).map(lambda p: f"{p[0]}{p[1]}")
    return st.lists(item, min_size=1, max_size=3, unique=True).map(",".join)


@st.composite
def rule_texts(draw: st.DrawFn, freq: str, *, set_pos: bool = False, wkst: bool = False) -> str:
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


FAKE_ZONES = (
    "Fake/EasternEurope",
    "Fake/HalfHour",
    "Fake/NegativeDST",
    "Fake/OneShot",
    "Fake/Plus0530",
)


def explicit_datetimes(start: datetime, days: int = 120) -> st.SearchStrategy[list[datetime]]:
    offsets = st.tuples(st.integers(0, days), st.integers(0, 24 * 60 - 1))
    return st.lists(
        offsets.map(
            lambda p: start + timedelta(days=p[0], minutes=p[1] - start.hour * 60 - start.minute)
        ),
        max_size=6,
    )


@st.composite
def numbered_yearly_rule_texts(draw: st.DrawFn) -> str:
    parts = ["FREQ=YEARLY"]
    if draw(st.booleans()):
        parts.append(f"INTERVAL={draw(st.integers(1, 3))}")
    use_week_no = draw(st.booleans())
    if use_week_no:
        weeks = st.one_of(st.integers(1, 51), st.integers(-50, -1))
        parts.append("BYWEEKNO=" + draw(_int_list(weeks)))
    if not use_week_no or draw(st.booleans()):
        year_days = st.one_of(st.integers(1, 366), st.integers(-366, -1))
        parts.append("BYYEARDAY=" + draw(_int_list(year_days, 4)))
    if draw(st.booleans()):
        parts.append("BYMONTH=" + draw(_int_list(st.integers(1, 12))))
    if draw(st.booleans()):
        parts.append("BYDAY=" + draw(plain_days))
    if draw(st.booleans()):
        parts.append("BYSETPOS=" + draw(_int_list(st.sampled_from((1, 2, -1, -2)), 2)))
    parts.append("WKST=" + draw(st.sampled_from(WEEKDAY_CODES)))
    return ";".join(parts)


SUMMARY_TEXT = st.text(
    st.one_of(
        st.characters(blacklist_categories=("Cs", "Cc")),
        st.sampled_from(["\n", ";", ",", "\\", ":", '"']),
    ),
    max_size=40,
)
EVENT_STARTS = (
    "DTSTART:{:%Y%m%dT%H%M%S}",
    "DTSTART:{:%Y%m%dT%H%M%S}Z",
    "DTSTART;TZID=Europe/Kyiv:{:%Y%m%dT%H%M%S}",
    "DTSTART;VALUE=DATE:{:%Y%m%d}",
)
EVENT_RULES = (
    "FREQ=DAILY;COUNT=5",
    "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=6",
    "FREQ=MONTHLY;BYDAY=-1FR;COUNT=4",
    "FREQ=YEARLY;BYMONTH=3,10;BYDAY=-1SU;COUNT=4",
)


@st.composite
def event_texts(draw: st.DrawFn) -> str:
    moment = draw(st.datetimes(datetime(2025, 1, 1), datetime(2027, 12, 31))).replace(microsecond=0)
    form = draw(st.sampled_from(EVENT_STARTS))
    all_day = "VALUE=DATE" in form
    lines = [
        "BEGIN:VEVENT",
        f"UID:{draw(st.uuids())}@recurkit.test",
        form.format(moment),
    ]
    summary = draw(SUMMARY_TEXT)
    if summary:
        escaped = summary.replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,")
        lines.append("SUMMARY:" + escaped.replace("\n", "\\n"))
    length = draw(st.sampled_from(("none", "dtend", "duration")))
    if length == "dtend":
        end = moment + timedelta(days=draw(st.integers(1, 3)), minutes=draw(st.integers(0, 600)))
        lines.append(form.replace("DTSTART", "DTEND").format(end))
    elif length == "duration":
        days, minutes = draw(st.integers(0, 3)), draw(st.integers(0, 600))
        lines.append(f"DURATION:P{days + all_day}D" if all_day else f"DURATION:P{days}DT{minutes}M")
    if draw(st.booleans()):
        lines.append("RRULE:" + draw(st.sampled_from(EVENT_RULES)))
    if draw(st.booleans()):
        lines.append("TRANSP:" + draw(st.sampled_from(("OPAQUE", "TRANSPARENT"))))
    if draw(st.booleans()):
        lines.append("STATUS:" + draw(st.sampled_from(("TENTATIVE", "CONFIRMED", "CANCELLED"))))
    return "\n".join([*lines, "END:VEVENT"])
