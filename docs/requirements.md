# RFC 5545 requirements

Each requirement has an ID. Tests include the ID in their name,
for example `test_rrule_07_count_and_until_are_exclusive`.
A rule that breaks a requirement raises `RuleValidationError` with its ID.

## RRULE (3.3.10)

- RRULE-01: FREQ MUST be specified.
- RRULE-02: Each rule part MUST be specified only once.
- RRULE-03: Rule parts MUST be accepted in any order.
- RRULE-04: FREQ MUST be the first rule part in text that RecurKit writes.
- RRULE-05: INTERVAL is a positive integer, default 1.
- RRULE-06: Value ranges: BYMONTH 1..12, BYMONTHDAY 1..31 or -31..-1, BYYEARDAY and BYSETPOS 1..366 or -366..-1, BYWEEKNO and the BYDAY ordinal 1..53 or -53..-1, COUNT is positive.
- RRULE-07: UNTIL and COUNT MUST NOT be used together.
- RRULE-08: UNTIL MUST have the same value type (DATE or DATE-TIME) as DTSTART.
- RRULE-09: If DTSTART is floating local time, UNTIL MUST also be floating.
- RRULE-10: If DTSTART is UTC or has a TZID, UNTIL MUST be UTC.
- RRULE-11: UNTIL is inclusive.
- RRULE-12: DTSTART SHOULD match the rule. An unmatched DTSTART is not added (D-03).
- RRULE-13: BYDAY MUST NOT have a number unless FREQ is MONTHLY or YEARLY.
- RRULE-14: BYMONTHDAY MUST NOT be used with FREQ=WEEKLY.
- RRULE-15: BYSETPOS MUST be used only together with another BYxxx part.
- RRULE-16: Invalid dates (e.g. February 30) MUST be ignored and MUST NOT be counted.
- RRULE-17: BYxxx parts are applied after FREQ and INTERVAL, in the order BYMONTH, BYMONTHDAY, BYDAY, BYSETPOS. COUNT and UNTIL are checked last.
- RRULE-18: Missing day, month or weekday is taken from DTSTART: WEEKLY without BYDAY takes its weekday; MONTHLY without BYDAY and BYMONTHDAY takes its day of the month; YEARLY without BYDAY, BYMONTHDAY, BYWEEKNO and BYYEARDAY takes its day of the month, and its month when BYMONTH is missing too.
- RRULE-19: BYMONTH, BYMONTHDAY and BYDAY either limit or expand the set, depending on FREQ (the table in 3.3.10).
- RRULE-20: A numbered BYDAY counts within the month for MONTHLY, and for YEARLY within the month if BYMONTH is set, otherwise within the year.
- RRULE-21: WKST (default MO) is the first day of the week. It matters for WEEKLY with INTERVAL > 1 and BYDAY.
- RRULE-22: BYSETPOS picks the n-th instance within one period. Negative values count from the end.
- RRULE-23: BYYEARDAY MUST NOT be used with FREQ DAILY, WEEKLY or MONTHLY.
- RRULE-24: BYWEEKNO MUST NOT be used unless FREQ is YEARLY.
- RRULE-25: BYDAY MUST NOT have a number with FREQ=YEARLY and BYWEEKNO.
- RRULE-26: Week 1 is the first week with at least four days in the year. Weeks start on WKST.
- RRULE-27: Value ranges of the time parts: BYHOUR 0..23, BYMINUTE 0..59, BYSECOND 0..59 (RecurKit does not support the leap second 60).
- RRULE-28: BYHOUR, BYMINUTE and BYSECOND MUST NOT be used with a DATE DTSTART.
- RRULE-29: For DAILY, WEEKLY, MONTHLY and YEARLY, BYHOUR, BYMINUTE and BYSECOND expand every day of the set into times of day; a missing hour, minute or second is taken from DTSTART. BYSETPOS counts these values within the period.

## DT: date and time (3.2.19, 3.3.4, 3.3.5)

- DT-01: DATE-TIME is floating local time, UTC (suffix `Z`) or local time with TZID.
- DT-02: TZID MUST NOT be used with UTC values.
- DT-03: A UTC offset in the value (e.g. `19980119T230000-0800`) MUST NOT be used.
- DT-04: TZID MUST NOT be used with DATE values.

## RULE: the rule model of RecurKit

- RULE-01: A `Rule` always has DTSTART and passes every RRULE check; `parse_rrule` returns `RuleParts`, and only `validate` (or the `Rule` constructor itself) turns them into a `Rule`.

## RSET: recurrence set (3.8.5)

- RSET-01: The set is RRULE plus RDATE minus EXDATE.
- RSET-02: EXDATE wins over RRULE and RDATE.
- RSET-03: A date produced by both RRULE and RDATE is counted once.
- RSET-04: RDATE and EXDATE values have the kind of DTSTART: DATE in an all-day series, floating time in a floating series, UTC or zoned time in a UTC or zoned series.

## TZ: time zones (3.3.5, 3.3.10, 3.2.19)

- TZ-01: A local time that occurs twice (end of DST) means the first one.
- TZ-02: An explicit local time inside a DST gap is shifted forward by the gap: 02:30 becomes 03:30. Applies to DTSTART, RDATE and EXDATE.
- TZ-03: Rule instances inside a DST gap MUST be ignored and MUST NOT be counted.
- TZ-04: Every TZID MUST be a known time zone, otherwise `TimeZoneError`.

The RFC contradicts itself about times in a DST gap. See D-05 in `docs/decisions.md`.

## ICAL: content lines (3.1)

- ICAL-01: A long line is folded with a line break plus one space or tab. Unfolding removes both.
- ICAL-02: A content line is `name;params:value`. A parameter value with `;`, `:` or `,` is quoted.
- ICAL-03: In TEXT values `\\`, `\;`, `\,` and `\n` are escapes.

## ICAL: components (3.4, 3.6)

- ICAL-04: A component starts with `BEGIN:name` and MUST end with `END:name` of the same name; components nest properly.
- ICAL-05: Every property belongs to a component; a content line outside `BEGIN`/`END` is an error.
- ICAL-06: Component and property names are case-insensitive.

## ICAL: calendar objects (3.4, 3.6, 3.7)

- ICAL-07: An iCalendar stream is one or more VCALENDAR objects; nothing else may stand at the top level.
- ICAL-08: A VCALENDAR MUST have PRODID and VERSION, each once; RecurKit reads VERSION 2.0 only.
- ICAL-09: Components that an application does not recognise (X- and IANA components) MUST be ignored.

## DUR: DURATION values (3.3.6)

- DUR-01: A duration is `[+|-]P` followed by weeks (`nW`) alone, or days (`nD`) and/or a time part `T` with hours, minutes and seconds in this order; an empty `P` or `T` part is invalid.
- DUR-02: Days and weeks are nominal (whole calendar days on the local clock); hours, minutes and seconds are exact.

## EVT: VEVENT (3.6.1, 3.8.2.2, 3.8.2.5, 3.8.2.7, 3.8.1.11)

- EVT-01: A VEVENT MUST have UID and DTSTART (RecurKit reads calendars without METHOD).
- EVT-02: DTEND and DURATION MUST NOT both occur in one VEVENT.
- EVT-03: DTEND is exclusive and MUST be later than DTSTART.
- EVT-04: DTEND MUST have the same value type as DTSTART and be floating local time exactly when DTSTART is.
- EVT-05: Without DTEND and DURATION an event with a DATE DTSTART lasts one day, one with a DATE-TIME DTSTART ends at DTSTART.
- EVT-06: With a DATE DTSTART, DURATION MUST be given in days or weeks.
- EVT-07: TRANSP is OPAQUE (default) or TRANSPARENT; STATUS of a VEVENT is TENTATIVE, CONFIRMED or CANCELLED.

## RID: RECURRENCE-ID and RANGE (3.8.4.4, 3.2.13)

- RID-01: RECURRENCE-ID MUST have the same value type as DTSTART of the recurring component.
- RID-02: RANGE is THISANDFUTURE; THISANDPRIOR is deprecated and MUST NOT be generated, RecurKit rejects it.
- RID-03: An instance is identified by UID together with RECURRENCE-ID, the original start of that instance.

## SER: series of instances (3.8.4.4, 3.8.1.11)

- SER-01: An override replaces the instance with the same RECURRENCE-ID; its start, end, summary and status come from the override.
- SER-02: A CANCELLED instance is not an occurrence of the series unless cancelled instances are asked for.
- SER-03: A moved instance belongs to the window that contains its new start, not its RECURRENCE-ID.
- SER-04: Changing or cancelling one instance is stored as an override with the UID and RECURRENCE-ID of that instance; other instances stay as they were.
- SER-05: Only an existing instance can be changed; the new end is not before the new start and has the value type of DTSTART.
- SER-06: Splitting a series at an instance ends the old rule with UNTIL at the instance before it and starts a series with a new UID at it; together they keep every instance and override.
- SER-07: Splitting a rule with COUNT keeps COUNT on both parts: the old part counts the rule instances before the cut, the new part the rest.
- SER-08: An override with RANGE=THISANDFUTURE changes its instance and every later one: each start moves by the same wall-clock shift as the override, and the length, summary, status and transparency come from the override; a later override, single or THISANDFUTURE, wins over it.

## Not implemented yet

- FREQ SECONDLY, MINUTELY, HOURLY and BYSECOND, BYMINUTE, BYHOUR.
- VTIMEZONE, VFREEBUSY (stages 6 and 7).
- RDATE values of type PERIOD.
- Leap second `60` in UNTIL (Python `datetime` cannot store it).
