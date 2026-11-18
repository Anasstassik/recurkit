"""Recurrence examples from RFC 5545, section 3.8.5.3, within the scope of RecurKit.

Every example uses DTSTART;TZID=America/New_York at 09:00 local time, as in the
RFC. Expected dates are copied from the RFC text (the first dates for rules
that run forever). Examples with BYWEEKNO, BYYEARDAY or HOURLY and finer
frequencies are out of scope and omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RfcExample:
    title: str
    dtstart: str
    rule: str
    expected: tuple[str, ...]
    exdates: tuple[str, ...] = ()
    rdates: tuple[str, ...] = ()
    tzid: str = "America/New_York"

    @property
    def freq(self) -> str:
        return self.rule.split("FREQ=")[1].split(";")[0]

    @property
    def start(self) -> datetime:
        return parse(self.dtstart)

    def expected_datetimes(self) -> list[datetime]:
        return [parse(value) for value in self.expected]


def parse(value: str) -> datetime:
    """``19970902`` -> 09:00 that day; ``19970902T153000`` -> the given time."""
    if "T" in value:
        return datetime.strptime(value, "%Y%m%dT%H%M%S")
    return datetime.strptime(value + "T090000", "%Y%m%dT%H%M%S")


def _days(prefix: str, days: str) -> tuple[str, ...]:
    """``_days("199709", "2 4 9")`` -> ``("19970902", "19970904", "19970909")``."""
    return tuple(f"{prefix}{int(day):02d}" for day in days.split())


def _month_range(prefix: str, first: int, last: int) -> tuple[str, ...]:
    return tuple(f"{prefix}{day:02d}" for day in range(first, last + 1))


EXAMPLES: tuple[RfcExample, ...] = (
    RfcExample(
        "Daily for 10 occurrences",
        "19970902",
        "FREQ=DAILY;COUNT=10",
        _days("199709", "2 3 4 5 6 7 8 9 10 11"),
    ),
    RfcExample(
        "Daily until December 24, 1997",
        "19970902",
        "FREQ=DAILY;UNTIL=19971224T000000Z",
        _month_range("199709", 2, 30)
        + _month_range("199710", 1, 31)
        + _month_range("199711", 1, 30)
        + _month_range("199712", 1, 23),
    ),
    RfcExample(
        "Every other day - forever",
        "19970902",
        "FREQ=DAILY;INTERVAL=2",
        _days("199709", "2 4 6 8 10 12 14 16 18 20 22 24 26 28 30") + _days("199710", "2 4 6"),
    ),
    RfcExample(
        "Every 10 days, 5 occurrences",
        "19970902",
        "FREQ=DAILY;INTERVAL=10;COUNT=5",
        _days("199709", "2 12 22") + _days("199710", "2 12"),
    ),
    RfcExample(
        "Every day in January, for 3 years (DAILY form)",
        "19980101",
        "FREQ=DAILY;UNTIL=20000131T140000Z;BYMONTH=1",
        _month_range("199801", 1, 31)
        + _month_range("199901", 1, 31)
        + _month_range("200001", 1, 31),
    ),
    RfcExample(
        "Every day in January, for 3 years (YEARLY form)",
        "19980101",
        "FREQ=YEARLY;UNTIL=20000131T140000Z;BYMONTH=1;BYDAY=SU,MO,TU,WE,TH,FR,SA",
        _month_range("199801", 1, 31)
        + _month_range("199901", 1, 31)
        + _month_range("200001", 1, 31),
    ),
    RfcExample(
        "Weekly for 10 occurrences",
        "19970902",
        "FREQ=WEEKLY;COUNT=10",
        _days("199709", "2 9 16 23 30") + _days("199710", "7 14 21 28") + _days("199711", "4"),
    ),
    RfcExample(
        "Weekly until December 24, 1997",
        "19970902",
        "FREQ=WEEKLY;UNTIL=19971224T000000Z",
        _days("199709", "2 9 16 23 30")
        + _days("199710", "7 14 21 28")
        + _days("199711", "4 11 18 25")
        + _days("199712", "2 9 16 23"),
    ),
    RfcExample(
        "Every other week - forever",
        "19970902",
        "FREQ=WEEKLY;INTERVAL=2;WKST=SU",
        _days("199709", "2 16 30") + _days("199710", "14 28") + _days("199711", "11 25"),
    ),
    RfcExample(
        "Weekly on Tuesday and Thursday for five weeks (UNTIL)",
        "19970902",
        "FREQ=WEEKLY;UNTIL=19971007T000000Z;WKST=SU;BYDAY=TU,TH",
        _days("199709", "2 4 9 11 16 18 23 25 30") + _days("199710", "2"),
    ),
    RfcExample(
        "Weekly on Tuesday and Thursday for five weeks (COUNT)",
        "19970902",
        "FREQ=WEEKLY;COUNT=10;WKST=SU;BYDAY=TU,TH",
        _days("199709", "2 4 9 11 16 18 23 25 30") + _days("199710", "2"),
    ),
    RfcExample(
        "Every other week on Monday, Wednesday and Friday until December 24, 1997",
        "19970901",
        "FREQ=WEEKLY;INTERVAL=2;UNTIL=19971224T000000Z;WKST=SU;BYDAY=MO,WE,FR",
        _days("199709", "1 3 5 15 17 19 29")
        + _days("199710", "1 3 13 15 17 27 29 31")
        + _days("199711", "10 12 14 24 26 28")
        + _days("199712", "8 10 12 22"),
    ),
    RfcExample(
        "Every other week on Tuesday and Thursday, for 8 occurrences",
        "19970902",
        "FREQ=WEEKLY;INTERVAL=2;COUNT=8;WKST=SU;BYDAY=TU,TH",
        _days("199709", "2 4 16 18 30") + _days("199710", "2 14 16"),
    ),
    RfcExample(
        "WKST=MO: every other week on Tuesday and Sunday",
        "19970805",
        "FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO",
        _days("199708", "5 10 19 24"),
    ),
    RfcExample(
        "WKST=SU: every other week on Tuesday and Sunday",
        "19970805",
        "FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU",
        _days("199708", "5 17 19 31"),
    ),
    RfcExample(
        "Monthly on the first Friday for 10 occurrences",
        "19970905",
        "FREQ=MONTHLY;COUNT=10;BYDAY=1FR",
        (
            "19970905",
            "19971003",
            "19971107",
            "19971205",
            "19980102",
            "19980206",
            "19980306",
            "19980403",
            "19980501",
            "19980605",
        ),
    ),
    RfcExample(
        "Monthly on the first Friday until December 24, 1997",
        "19970905",
        "FREQ=MONTHLY;UNTIL=19971224T000000Z;BYDAY=1FR",
        ("19970905", "19971003", "19971107", "19971205"),
    ),
    RfcExample(
        "Every other month on the first and last Sunday, for 10 occurrences",
        "19970907",
        "FREQ=MONTHLY;INTERVAL=2;COUNT=10;BYDAY=1SU,-1SU",
        (
            "19970907",
            "19970928",
            "19971102",
            "19971130",
            "19980104",
            "19980125",
            "19980301",
            "19980329",
            "19980503",
            "19980531",
        ),
    ),
    RfcExample(
        "Monthly on the second-to-last Monday for 6 months",
        "19970922",
        "FREQ=MONTHLY;COUNT=6;BYDAY=-2MO",
        ("19970922", "19971020", "19971117", "19971222", "19980119", "19980216"),
    ),
    RfcExample(
        "Monthly on the third-to-the-last day - forever",
        "19970928",
        "FREQ=MONTHLY;BYMONTHDAY=-3",
        ("19970928", "19971029", "19971128", "19971229", "19980129", "19980226"),
    ),
    RfcExample(
        "Monthly on the 2nd and 15th for 10 occurrences",
        "19970902",
        "FREQ=MONTHLY;COUNT=10;BYMONTHDAY=2,15",
        _days("199709", "2 15")
        + _days("199710", "2 15")
        + _days("199711", "2 15")
        + _days("199712", "2 15")
        + _days("199801", "2 15"),
    ),
    RfcExample(
        "Monthly on the first and last day for 10 occurrences",
        "19970930",
        "FREQ=MONTHLY;COUNT=10;BYMONTHDAY=1,-1",
        (
            "19970930",
            "19971001",
            "19971031",
            "19971101",
            "19971130",
            "19971201",
            "19971231",
            "19980101",
            "19980131",
            "19980201",
        ),
    ),
    RfcExample(
        "Every 18 months on the 10th thru 15th, for 10 occurrences",
        "19970910",
        "FREQ=MONTHLY;INTERVAL=18;COUNT=10;BYMONTHDAY=10,11,12,13,14,15",
        _days("199709", "10 11 12 13 14 15") + _days("199903", "10 11 12 13"),
    ),
    RfcExample(
        "Every Tuesday, every other month",
        "19970902",
        "FREQ=MONTHLY;INTERVAL=2;BYDAY=TU",
        _days("199709", "2 9 16 23 30")
        + _days("199711", "4 11 18 25")
        + _days("199801", "6 13 20 27")
        + _days("199803", "3 10 17 24 31"),
    ),
    RfcExample(
        "Every Friday the 13th (DTSTART excluded by EXDATE)",
        "19970902",
        "FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13",
        ("19980213", "19980313", "19981113", "19990813", "20001013"),
        exdates=("19970902",),
    ),
    RfcExample(
        "The first Saturday that follows the first Sunday of the month",
        "19970913",
        "FREQ=MONTHLY;BYDAY=SA;BYMONTHDAY=7,8,9,10,11,12,13",
        (
            "19970913",
            "19971011",
            "19971108",
            "19971213",
            "19980110",
            "19980207",
            "19980307",
            "19980411",
            "19980509",
            "19980613",
        ),
    ),
    RfcExample(
        "The third instance into the month of one of Tuesday, Wednesday or Thursday",
        "19970904",
        "FREQ=MONTHLY;COUNT=3;BYDAY=TU,WE,TH;BYSETPOS=3",
        ("19970904", "19971007", "19971106"),
    ),
    RfcExample(
        "The second-to-last weekday of the month",
        "19970929",
        "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-2",
        ("19970929", "19971030", "19971127", "19971230", "19980129", "19980226", "19980330"),
    ),
    RfcExample(
        "Invalid dates are ignored: the 15th and 30th of each month",
        "20070115",
        "FREQ=MONTHLY;BYMONTHDAY=15,30;COUNT=5",
        ("20070115", "20070130", "20070215", "20070315", "20070330"),
    ),
    RfcExample(
        "Yearly in June and July for 10 occurrences",
        "19970610",
        "FREQ=YEARLY;COUNT=10;BYMONTH=6,7",
        (
            "19970610",
            "19970710",
            "19980610",
            "19980710",
            "19990610",
            "19990710",
            "20000610",
            "20000710",
            "20010610",
            "20010710",
        ),
    ),
    RfcExample(
        "Every other year on January, February and March for 10 occurrences",
        "19970310",
        "FREQ=YEARLY;INTERVAL=2;COUNT=10;BYMONTH=1,2,3",
        (
            "19970310",
            "19990110",
            "19990210",
            "19990310",
            "20010110",
            "20010210",
            "20010310",
            "20030110",
            "20030210",
            "20030310",
        ),
    ),
    RfcExample(
        "Every 20th Monday of the year, forever",
        "19970519",
        "FREQ=YEARLY;BYDAY=20MO",
        ("19970519", "19980518", "19990517"),
    ),
    RfcExample(
        "Every Thursday in March, forever",
        "19970313",
        "FREQ=YEARLY;BYMONTH=3;BYDAY=TH",
        _days("199703", "13 20 27") + _days("199803", "5 12 19 26") + _days("199903", "4 11 18 25"),
    ),
    RfcExample(
        "Every Thursday, but only during June, July, and August, forever",
        "19970605",
        "FREQ=YEARLY;BYDAY=TH;BYMONTH=6,7,8",
        _days("199706", "5 12 19 26")
        + _days("199707", "3 10 17 24 31")
        + _days("199708", "7 14 21 28")
        + _days("199806", "4 11 18 25"),
    ),
    RfcExample(
        "U.S. Presidential Election day, every 4 years",
        "19961105",
        "FREQ=YEARLY;INTERVAL=4;BYMONTH=11;BYDAY=TU;BYMONTHDAY=2,3,4,5,6,7,8",
        ("19961105", "20001107", "20041102"),
    ),
)
