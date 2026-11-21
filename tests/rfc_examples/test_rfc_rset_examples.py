from datetime import datetime
from itertools import islice

import pytest

from recurkit.ical import parse_recurrence
from tests.rfc_examples.data import EXAMPLES, RfcExample


def _ics(example: RfcExample) -> str:
    lines = [f"DTSTART;TZID={example.tzid}:{example.dtstart}T090000", f"RRULE:{example.rule}"]
    if example.exdates:
        lines.append(
            f"EXDATE;TZID={example.tzid}:" + ",".join(f"{d}T090000" for d in example.exdates)
        )
    return "\r\n".join(lines)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.title)
def test_rfc_examples_as_ics_text_in_new_york(example: RfcExample) -> None:
    rset = parse_recurrence(_ics(example))
    expected = example.expected_datetimes()
    values = list(islice(rset, len(expected) + 1))
    walls = [v.replace(tzinfo=None) for v in values]  # type: ignore[call-arg]
    assert walls[: len(expected)] == expected
    if not rset.rule.is_infinite:
        assert len(walls) == len(expected)


def test_rfc_rdate_and_exdate_property_examples() -> None:
    text = "\r\n".join(
        [
            "DTSTART;TZID=America/New_York:19970714T083000",
            "RRULE:FREQ=WEEKLY;COUNT=3",
            "RDATE:19970714T123000Z",
            "RDATE;TZID=America/New_York:19970714T083000",
            "RDATE;VALUE=DATE-TIME:19970101T180000Z,19970120T070000Z",
            "EXDATE:19970721T123000Z",
        ]
    )
    walls = [v.replace(tzinfo=None) for v in parse_recurrence(text)]  # type: ignore[call-arg]
    assert walls == [
        datetime(1997, 1, 1, 13),
        datetime(1997, 1, 20, 2),
        datetime(1997, 7, 14, 8, 30),
        datetime(1997, 7, 28, 8, 30),
    ]
