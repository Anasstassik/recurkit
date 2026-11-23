from itertools import islice
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import Calendar, RecurKitError, parse_ics

LINES = (
    (Path(__file__).resolve().parents[1] / "data" / "ics" / "team.ics")
    .read_text("utf-8")
    .splitlines()
)
VALUES = st.one_of(
    st.sampled_from(
        [
            "",
            "20260230T100000",
            "20260101",
            "PT",
            "P1W2D",
            "FREQ=DAILY;COUNT=0",
            "FREQ=WEEKLY;BYDAY=2TU",
            "Mars/Olympus",
            "VEVENT",
            "X-FOO",
            '"',
            "\\q",
        ]
    ),
    st.text(max_size=12),
)


def _accepts_or_fails_cleanly(text: str) -> None:
    try:
        calendar = parse_ics(text)
    except RecurKitError:
        return
    assert isinstance(calendar, Calendar)
    for event in calendar:
        for start in islice(event.starts(), 30):
            event.end_for(start)


@settings(max_examples=300, deadline=1000)
@given(
    edits=st.lists(
        st.tuples(st.sampled_from(("drop", "copy")), st.integers(0, len(LINES) - 1)), max_size=4
    )
)
def test_deleted_and_duplicated_lines_give_calendar_or_library_error(
    edits: list[tuple[str, int]],
) -> None:
    lines = list(LINES)
    for kind, index in edits:
        index %= len(lines) or 1
        if not lines:
            break
        if kind == "drop":
            del lines[index]
        else:
            lines.insert(index, lines[index])
    _accepts_or_fails_cleanly("\r\n".join(lines))


@settings(max_examples=300, deadline=1000)
@given(index=st.integers(0, len(LINES) - 1), cut=st.integers(0, 80), pad=st.sampled_from(" \t"))
def test_broken_folding_gives_calendar_or_library_error(index: int, cut: int, pad: str) -> None:
    lines = list(LINES)
    line = lines[index]
    lines[index : index + 1] = [line[:cut], pad + line[cut:]]
    _accepts_or_fails_cleanly("\r\n".join(lines))
    _accepts_or_fails_cleanly("\r\n".join(lines).replace("\r\n" + pad, "\r\n", 1))


@settings(max_examples=400, deadline=1000)
@given(index=st.integers(0, len(LINES) - 1), value=VALUES, keep_params=st.booleans())
def test_replaced_values_give_calendar_or_library_error(
    index: int, value: str, keep_params: bool
) -> None:
    lines = list(LINES)
    head, _, _ = lines[index].partition(":")
    name = head if keep_params else head.split(";")[0]
    lines[index] = f"{name}:{value}"
    _accepts_or_fails_cleanly("\r\n".join(lines))
