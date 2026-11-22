from datetime import UTC, date, datetime

import pytest

from recurkit import Rule, describe
from recurkit.rule.describe import join_words, ordinal

START = datetime(2026, 11, 16, 9, 30)

CASES = [
    ("FREQ=DAILY", "daily at 09:30"),
    ("FREQ=DAILY;INTERVAL=10;COUNT=5", "every 10 days at 09:30, 5 times"),
    ("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE", "every other week on Monday and Wednesday at 09:30"),
    ("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", "weekly on weekdays at 09:30"),
    (
        "FREQ=WEEKLY;BYDAY=TU,SU;WKST=SU",
        "weekly on Tuesday and Sunday at 09:30 with weeks starting on Sunday",
    ),
    ("FREQ=MONTHLY;BYDAY=-1FR;COUNT=6", "monthly on the last Friday at 09:30, 6 times"),
    (
        "FREQ=MONTHLY;INTERVAL=3;BYDAY=2TU,-2FR",
        "every 3 months on the second Tuesday and the 2nd to last Friday at 09:30",
    ),
    ("FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1", "monthly on the last weekday at 09:30"),
    (
        "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYSETPOS=3",
        "monthly on the third day at 09:30",
    ),
    (
        "FREQ=MONTHLY;BYDAY=TU,TH;BYSETPOS=1,-1",
        "monthly on Tuesday and Thursday keeping the 1st and last at 09:30",
    ),
    ("FREQ=MONTHLY;BYMONTHDAY=1,15", "monthly on the 1st and 15th at 09:30"),
    ("FREQ=MONTHLY;BYMONTHDAY=-1", "monthly on the last day of the month at 09:30"),
    (
        "FREQ=YEARLY;BYMONTH=1,3;BYMONTHDAY=1",
        "yearly in January and March on the 1st at 09:30",
    ),
    ("FREQ=YEARLY;BYWEEKNO=20;BYDAY=MO", "yearly in week 20 on Monday at 09:30"),
    (
        "FREQ=YEARLY;BYWEEKNO=-1;BYDAY=FR",
        "yearly in the last week of the year on Friday at 09:30",
    ),
    (
        "FREQ=YEARLY;BYYEARDAY=1,100,-1",
        "yearly on the 1st, 100th and last day of the year at 09:30",
    ),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_describe_rules(text: str, expected: str) -> None:
    assert describe(Rule.parse(text, START)) == expected


def test_describe_until_and_all_day_series() -> None:
    utc_rule = Rule.parse("FREQ=DAILY;UNTIL=20261231T220000Z", START.replace(tzinfo=UTC))
    assert describe(utc_rule) == "daily at 09:30, until 31 December 2026 22:00 UTC"
    all_day = Rule.parse("FREQ=YEARLY;UNTIL=20300101", date(2026, 1, 1))
    assert describe(all_day) == "yearly, until 1 January 2030"
    assert describe(Rule.parse("FREQ=YEARLY;COUNT=1", date(2026, 1, 1))) == "yearly, once"


@pytest.mark.parametrize(
    ("n", "text"),
    [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th"), (13, "13th"),
     (21, "21st"), (22, "22nd"), (101, "101st"), (111, "111th"), (-1, "last"),
     (-2, "2nd to last"), (-23, "23rd to last")],
)
def test_ordinals(n: int, text: str) -> None:
    assert ordinal(n) == text


def test_join_words() -> None:
    assert join_words([]) == ""
    assert join_words(["a"]) == "a"
    assert join_words(["a", "b"]) == "a and b"
    assert join_words(["a", "b", "c"]) == "a, b and c"
