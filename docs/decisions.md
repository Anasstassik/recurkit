# Design decisions

Places where RecurKit interprets RFC 5545 or differs from the design document.

## D-01. Rule is a pure model

`Rule` only stores and parses a rule (`Rule.parse(text, dtstart, tzid)`).
Generating dates is done by `expand`: `occurrences(rule)`, `between(rule, a, b)`,
`after(rule, x)`, for a rule without TZID (D-17). A method on `Rule` would make `rule` import `expand` and break
the layers `recurrence_set -> expand -> rule`. Method-style calls are on
`RecurrenceSet`.

## D-02. The generator works in local time

`expand` produces naive wall-clock times and knows nothing about time zones.
To skip times inside a DST gap (TZ-03), it takes a function
`is_valid(local) -> bool`. `recurrence_set` passes one that asks the time zone
provider.

## D-03. An unmatched DTSTART is not added (RRULE-12)

The RFC says the result is undefined if DTSTART does not match the rule.
RecurKit never adds DTSTART by force: a matching DTSTART comes out of the
generator as the first date, an unmatched one is skipped, and COUNT counts only
rule dates. dateutil does the same.

## D-04. `calendar_math` is the bottom layer

`Weekday` lives in `calendar_math`, and `rule` and `expand` import it.
`calendar_math` imports nothing from RecurKit.

## D-05. Times in a DST gap (TZ-02, TZ-03)

The RFC contradicts itself: 3.3.10 says rule instances in a gap MUST be ignored,
3.8.5.3 says they are shifted like explicit times. RecurKit does this:

- Rule instance: in a gap it is dropped and not counted in COUNT; in a fold it is the first occurrence.
- DTSTART: in a gap it is shifted (02:30 -> 03:30) and counted; in a fold it is the first occurrence.
- RDATE / EXDATE: in a gap it is shifted; in a fold it is the first occurrence.

EXDATE is compared as a UTC instant, so it can be in any zone. A UTC UNTIL of a
zoned rule is converted to wall-clock time by `recurrence_set`.

## D-06. Differences from dateutil

The differential tests skip these cases. RecurKit follows the RFC.

- `BYDAY=MO,-1FR`: dateutil intersects the two lists; RecurKit gives every Monday and the last Friday.
- DAILY with COUNT across a DST gap: dateutil counts the shifted time; RecurKit drops it and counts the next day (TZ-03).
- `YEARLY;BYMONTH=7;BYDAY=51SA`: dateutil raises IndexError; RecurKit returns no date for that period.
- BYWEEKNO for the last week of the previous year: dateutil is off by one week; RecurKit uses the day's own week-year (RRULE-26).
- BYSETPOS in the first week of a WEEKLY rule when DTSTART is not on WKST: dateutil uses only the days from DTSTART; RecurKit uses the whole week, then drops days before DTSTART (RRULE-22).
- Negative BYWEEKNO for days in week 1 of the next year: dateutil does not check it; RecurKit counts from the end of that week-year.

## D-07. BYWEEKNO and BYYEARDAY

Optional in the design document, added in milestone 1. A YEARLY rule keeps the
days that pass every given part, in the order BYMONTH, BYWEEKNO, BYYEARDAY,
BYMONTHDAY, BYDAY. BYWEEKNO without BYDAY gives all seven days of the week, as
in dateutil. Defaults from DTSTART are not used when either part is present.

A week can cross New Year: week 53 of 2020 runs from 28 December 2020 to
3 January 2021. Its days belong to the calendar year they fall in, so BYSETPOS
counts 1 and 3 January among the dates of 2021, as dateutil does. For
`FREQ=YEARLY;BYWEEKNO=6,53;BYDAY=FR,SU;BYSETPOS=2` the 2021 value is
3 January 2021, not 14 February 2021. RFC 5545 does not decide this.

## D-08. Content lines are parsed before stage 4

`recurkit.ical` already unfolds content lines and builds a `RecurrenceSet` from
DTSTART, RRULE, RDATE and EXDATE. VCALENDAR, VEVENT, DURATION and the CLI stay
in stage 4.

## D-09. `series` and `availability` are packages

The design document lists `series.py` and `availability.py` as single modules
of about 550 and 600 lines. They become the packages `recurkit/series/` and
`recurkit/availability/`, like `rule/` and `expand/`. Imports stay as planned:
`from recurkit.series import Series`.

## D-10. The VTIMEZONE engine uses the rule generator

`timezones/vtimezone_provider.py` computes transitions of STANDARD and
DAYLIGHT observances with `expand`, as the design document asks. `timezones`
stays a separate layer: it may import `expand`, but `expand`, `rule` and
`calendar_math` still never import `timezones` (import-linter contract).

## D-11. The CLI is not core code

`recurkit/cli.py` and `recurkit/__main__.py` are not counted as core lines:
`pygount --format=summary --names-to-skip="cli.py,__main__.py" recurkit`.
The bug lab runner lives in `tools/`, outside the package.

## D-12. DURATION follows the RFC grammar strictly

`PT1H20S` (hours and seconds without minutes) and `P1W2D` (weeks with days) are
rejected, as the grammar of RFC 5545 3.3.6 allows neither. Days and weeks are
added on the local clock, hours, minutes and seconds as exact time (DUR-02), so
`P1D` across a DST change keeps the wall-clock time and `PT24H` does not.

## D-13. Overrides belong to their master event

`parse_ics` attaches every VEVENT with RECURRENCE-ID to the VEVENT with the
same UID and no RECURRENCE-ID (`Event.overrides`). RECURRENCE-ID is compared
as an instant, so it may be written in UTC or in another zone than the master.
An override whose master is not in the file stays a standalone event, because
the RFC allows sending single instances. Two masters with one UID, or two
overrides of one instance, are an `ICalParseError`. Applying overrides to the
instances of a series is done by `recurkit.series` (stage 5).

## D-14. A series is a master with its instances

`recurkit.series.Series` builds `Instance` values from the master event and
its overrides. An override must keep the value kind of DTSTART (DATE,
floating or zoned DATE-TIME) both in RECURRENCE-ID and in its new start,
otherwise it is a `SeriesError`. An override whose RECURRENCE-ID is not an
instance of the rule is still listed, as RFC 5545 allows adding instances this
way. Instances come in order of their start; cancelled ones are skipped unless
`include_cancelled=True`.

## D-15. Rules without any value are valid

`FREQ=DAILY;BYMONTH=2;BYMONTHDAY=30` passes validation, as RFC 5545 does not
forbid it, but it has no value. Iterating it scans every period up to the year
9999 before it ends (about 15 seconds), as dateutil does. Callers that need a
quick answer query a window (`between`) instead of iterating the whole rule.
The generators of the property tests skip such rules.

## D-16. What a value of a zoned set carries

A value of a zoned set is a `datetime` with the fixed UTC offset of its own
instant, named by the TZID. It is an instant, not a zone: adding `timedelta`
to it keeps the offset, so the result can be an hour off the wall clock across
a DST change. Arithmetic on nominal durations (days and weeks) is done by the
library on the local clock: `Duration.add_to_local`, `Event.end_for`
(DUR-02), and the next value of a set always comes from the set.

## D-17. `expand` takes floating rules; `until=` is a horizon

`expand` works on local time only (D-02), so a rule with a TZID cannot go
through it: its UNTIL is a UTC instant (RRULE-10) that only a time zone can
turn into a wall-clock time. `occurrences`, `between`, `after`, `before` and
`is_occurrence` raise `TimeZoneError` for such a rule at the call, before any
value is produced (Bug 3 of the midterm review). A zoned rule is expanded
through `RecurrenceSet`, which converts UNTIL to local time once, when the set
is built, and hands `expand` the same rule without its TZID.

The `until=` argument of these functions is a horizon on top of the rule: the
earlier of `until=` and the rule's own UNTIL wins, so a query never returns a
value that is not in the rule. A naive or UTC `until=` is first brought to the
kind of DTSTART. The contract test in `tests/unit/test_until_horizon.py` checks
all four functions against `RecurrenceSet` with a horizon before, at and after
UNTIL.

## D-18. The range of dates

A floating or all-day series works on every day from 0001-01-01 to
9999-12-31. A week that starts before 0001-01-01 (WKST=SU and DTSTART on
Monday 0001-01-01) is cut at the first day of the calendar, and the weekdays
of a week are counted from its first existing day. A zoned value is supported
while its UTC instant lies in the same years: the provider never looks at a
day outside them, and a local time that has no such instant (0001-01-01 00:30
at UTC+2, or 9999-12-31 23:30 in New York) raises `TimeZoneError`, never
`OverflowError` (Bug 4 of the midterm review). A query bound in UTC near either
end works; a naive bound is a local time and follows the same rule.

## D-19. The kind of an RDATE or EXDATE value

A series has one of four kinds: all-day, floating, UTC or zoned. An explicit
value of a UTC series may be written in UTC or with any TZID; it is stored in
UTC (Bug 1 of the midterm review). A floating series accepts only floating
values: a UTC value or a value with a TZID has no meaning on a clock that is
not tied to a zone, so `parse_recurrence` and `parse_ics` raise
`ICalParseError` with the line number, and `RecurrenceSet` raises
`RuleValidationError` (RSET-04), never a bare `TypeError`.

`TimeZoneError` stays a `RecurKitError` that is not a `ValueError`: an unknown
or unusable zone is a problem of the zone data, not of the value the caller
passed, and the parsers catch `ValueError` to turn bad values into syntax
errors, which must not swallow zone errors.

## D-20. A `Rule` is valid by construction

`parse_rrule` returns `RuleParts`: the parts as written, with an optional
DTSTART, which may break any RRULE check. `Rule` is a `RuleParts` whose
constructor runs every check and needs DTSTART (RULE-01), so a rule built
directly, by `dataclasses.replace` or by `validate` is always valid, and the
expansion and `RecurrenceSet` never see an invalid rule (cluster A of the
midterm review). Tests of the validator build `RuleParts`.

## D-21. A set decides its kind once and keeps its zone in a `ZoneFrame`

`RecurrenceSet` works out its `ValueKind` (all-day, floating, UTC or zoned)
from DTSTART and the TZID when it is built, and every check of an RDATE,
EXDATE or query bound asks that kind (`ValueKind.accepts`) instead of looking
at `date`, `datetime` and `tzinfo` again (cluster B of the midterm review). A
zoned set holds one frozen `ZoneFrame(provider, tzid)`, which checks the zone
once and does every conversion: `place` (a wall time or an instant to a value
in the zone), `to_local`, `exists` and `local_window`. A set without a zone has
no frame, so there is no provider without a TZID or TZID without a provider.
`local_window` widens a window of instants by one day of local time on each
side, because in a DST fold a wall time later than the bound's wall time can be
an earlier instant; a unit test of the frame fails without the margin.

## D-22. Each check of the expansion happens in one place

The expansion builds its limit filters and its week numbering once per rule
or year and passes them on: `expand_period`, `period_occurrences` and
`week_no_matches` take them as required arguments, with no fallback that
computes them again (cluster C of the midterm review). A numbered weekday in a
plan is an `NthWeekday` whose number is an `int`, so no expander checks for a
missing number. Code outside `recurkit.expand` imports only the package:
`candidates(rule, start=None, ...)` is the one entry point that walks from
DTSTART or jumps to `start`, and an import-linter contract forbids importing
the submodules of `expand` from `recurrence_set`, `ical`, `series` and `cli`.

## D-23. THISANDFUTURE overrides are applied, not split

A VEVENT with `RECURRENCE-ID;RANGE=THISANDFUTURE` keeps the UID of its
series, so `Series` applies it in place instead of calling `split`, which
needs a new UID. The override moves its instance and every later one by the
shift between its DTSTART and its RECURRENCE-ID, measured in the wall time of
the series zone, so a 10:00 → 11:30 change stays at 11:30 after a DST change
(SER-08). Length, SUMMARY, STATUS and TRANSP come from the override, so a
cancelled THISANDFUTURE override ends the series. The latest such override at
or before an instance applies, and a single override of that instance wins
over it. A window query widens its search by the largest shift, so an instance
moved into the window from outside is found. Instances keep the order of the
rule; a shift larger than the gap between two instances can reorder them, and
RecurKit does not reorder them back. `load_series(calendar)` builds one
`Series` per master by UID; an override without its master stays a standalone
event, as in D-13. `recurkit expand` lists the instances of each series, with
moved, cancelled and THISANDFUTURE overrides applied.

## D-24. Times of day before sub-daily frequencies

BYHOUR, BYMINUTE and BYSECOND come first for the frequencies RecurKit already
expands. A plan keeps the times of day of the rule (`Rule.times_of_day`):
every combination of the given hours, minutes and seconds, with a missing part
taken from DTSTART, in the zone of DTSTART. Each day of a period gives one
value per time of day, and BYSETPOS then counts values, not days, as RFC 5545
and dateutil do (RRULE-29). Values before DTSTART on its own day are skipped
like any value before DTSTART. A second of 60 is rejected (RRULE-27), as in
DATE-TIME values.

## D-25. Sub-daily periods are counted in wall-clock time

HOURLY, MINUTELY and SECONDLY rules have their own generator
(`expand/subdaily.py`), because their periods are shorter than the days the
other expanders work with. A period starts at DTSTART cut to the start of its
hour, minute or second plus a multiple of INTERVAL units, so window queries
jump straight to the period of a bound. A period whose day fails BYMONTH,
BYYEARDAY, BYMONTHDAY or BYDAY, or whose hour fails BYHOUR (or minute fails
BYMINUTE for SECONDLY), is skipped together with the rest of that day, hour or
minute, so a rule that matches one day a week costs about one period per day.
Like the other frequencies, a zoned rule is expanded in local wall-clock time,
as dateutil does: across a DST change an HOURLY series keeps its wall times,
and the gap and fold rules of D-05 place each value.
