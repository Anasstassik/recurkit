from itertools import islice
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import parse_ics
from recurkit.ical import Event, format_calendar
from tests.strategies import event_texts

DATA = Path(__file__).resolve().parents[1] / "data" / "ics"


def _key(event: Event) -> tuple[object, ...]:
    starts = list(islice(event.starts(), 8))
    return (
        event.uid,
        event.summary,
        event.start,
        event.end,
        event.transparency,
        event.status,
        event.rdates,
        event.exdates,
        event.tzid,
        starts,
        [event.end_for(start) for start in starts],
    )


@settings(max_examples=150, deadline=None)
@given(events=st.lists(event_texts(), min_size=1, max_size=3))
def test_written_events_parse_back_to_the_same_events(events: list[str]) -> None:
    text = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\n" + "\n".join(events) + "\nEND:VCALENDAR"
    calendar = parse_ics(text)
    again = parse_ics(format_calendar(calendar))
    assert [_key(event) for event in again] == [_key(event) for event in calendar]
    assert again.prodids == ("-//t//EN",)


def test_sample_file_round_trips() -> None:
    calendar = parse_ics((DATA / "team.ics").read_text("utf-8"))
    written = format_calendar(calendar)
    assert all(len(line.encode("utf-8")) <= 75 for line in written.split("\r\n"))
    assert [_key(event) for event in parse_ics(written)] == [_key(event) for event in calendar]
