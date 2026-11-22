# Design decisions

Places where RecurKit interprets RFC 5545 or differs from the design document.

## D-01. Rule is a pure model

`Rule` only stores and parses a rule (`Rule.parse(text, dtstart, tzid)`).
Generating dates is done by `expand`: `occurrences(rule)`, `between(rule, a, b)`,
`after(rule, x)`. A method on `Rule` would make `rule` import `expand` and break
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

## D-08. Content lines are parsed before stage 4

`recurkit.ical` already unfolds content lines and builds a `RecurrenceSet` from
DTSTART, RRULE, RDATE and EXDATE. VCALENDAR, VEVENT, DURATION and the CLI stay
in stage 4.
