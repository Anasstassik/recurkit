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
