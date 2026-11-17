# Design decisions

Decisions that interpret RFC 5545 or deviate from the design document draft.
Each entry names the requirement IDs from `docs/requirements.md` it concerns.

## D-01. Rule is a pure model; generator functions live in `expand`

The design document lists `rule.occurrences()`, `rule.between()` and
`rule.after()` as working names. A method on `Rule` would force `recurkit.rule`
to import `recurkit.expand`, which breaks the layering
`recurrence_set -> expand -> rule`. Therefore:

- `recurkit.rule.Rule` is an immutable model with `Rule.parse(text, dtstart, tzid)`;
- `recurkit.expand` provides `occurrences(rule)`, `between(rule, a, b)` and
  `after(rule, x)`;
- the method-style API lives on `RecurrenceSet`, which sits on top of both.

## D-02. The generator works with local time only

`expand` produces naive local date-times (as RFC 5545 describes: "every day at
10:00" means 10:00 on the wall clock). It knows nothing about time zones. RRULE
instances with a nonexistent local time must not be counted in COUNT (TZ-03), so
the iterator accepts a neutral predicate `is_valid(local) -> bool`;
`recurrence_set` passes a check backed by the time zone provider.

## D-03. An unsynchronized DTSTART is not added to the set (RRULE-12)

RFC 5545 says the set generated with a DTSTART that does not match the rule is
undefined. The design document example (DTSTART 2026-01-06,
`FREQ=MONTHLY;BYDAY=2TU;COUNT=6` -> 13.01 ... 09.06) does not include DTSTART,
and `dateutil.rrule` behaves the same way. RecurKit never force-adds DTSTART:
a synchronized DTSTART is produced by the generator itself as the first
instance, an unsynchronized one is skipped and COUNT counts rule dates only.

## D-04. `calendar_math` is the bottom layer

`Weekday` lives in `calendar_math` and is imported by `rule` and `expand`.
"Separate" in the design document is read as "a base layer without
dependencies": import-linter forbids only imports in the opposite direction.
