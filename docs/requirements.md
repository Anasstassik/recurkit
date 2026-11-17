# RFC 5545 requirements catalog

RFC 5545 does not number its requirements. This catalog gives an identifier to
every statement that RecurKit implements in milestone 1 (stages 1-3 of the design
document): rule syntax and validation, the date generator, recurrence sets and
time zones. Every identifier has at least one test whose name contains it, for
example `test_rrule_07_count_and_until_are_exclusive`.

Columns:

- **Level**: the keyword from the RFC text (MUST, MUST NOT, SHOULD) or
  *normative* for descriptive normative text and the ABNF grammar that has no
  keyword but defines behaviour.
- **Enforced in**: the module that implements the requirement.
- Violations detected in a rule raise `RuleValidationError` carrying the ID.

## RRULE: recurrence rule (section 3.3.10)

| ID | Section | Level | Requirement | Enforced in |
|---|---|---|---|---|
| RRULE-01 | 3.3.10 | MUST | The FREQ rule part MUST be specified in the recurrence rule. | `rule/parser.py` |
| RRULE-02 | 3.3.10 | MUST | Individual rule parts MUST only be specified once. | `rule/parser.py` |
| RRULE-03 | 3.3.10 | MUST | Compliant applications MUST accept rule parts ordered in any sequence. | `rule/parser.py` |
| RRULE-04 | 3.3.10 | MUST | For backward compatibility FREQ MUST be the first rule part specified in a RECUR value (applies to text RecurKit writes). | `rule/model.py` (`to_text`) |
| RRULE-05 | 3.3.10 | normative | INTERVAL is a positive integer; the default value is 1. | `rule/validation.py` |
| RRULE-06 | 3.3.10 (ABNF) | normative | Value ranges: BYMONTH 1..12, BYMONTHDAY 1..31 or -31..-1, BYSETPOS 1..366 or -366..-1, BYDAY ordinal 1..53 or -53..-1, COUNT is a positive integer. | `rule/validation.py` |
| RRULE-07 | 3.3.10 | MUST NOT | UNTIL and COUNT MUST NOT occur in the same recur. | `rule/validation.py` |
| RRULE-08 | 3.3.10 | MUST | The value of UNTIL MUST have the same value type (DATE or DATE-TIME) as DTSTART. | `rule/validation.py` |
| RRULE-09 | 3.3.10 | MUST | If DTSTART is a date with local (floating) time, UNTIL MUST also be a date with local time. | `rule/validation.py` |
| RRULE-10 | 3.3.10 | MUST | If DTSTART is a date with UTC time or with local time and a time zone reference, UNTIL MUST be a date with UTC time. | `rule/validation.py` |
| RRULE-11 | 3.3.10 | normative | UNTIL bounds the recurrence in an inclusive manner: a synchronized UNTIL value is the last instance. | `expand/iterator.py` |
| RRULE-12 | 3.3.10 | SHOULD | DTSTART SHOULD be synchronized with the rule; a set generated from an unsynchronized DTSTART is undefined (RecurKit decision: see `docs/decisions.md`, D-03). | `expand/iterator.py` |
| RRULE-13 | 3.3.10 | MUST NOT | BYDAY MUST NOT have a numeric value unless FREQ is MONTHLY or YEARLY. | `rule/validation.py` |
| RRULE-14 | 3.3.10 | MUST NOT | BYMONTHDAY MUST NOT be specified when FREQ is WEEKLY. | `rule/validation.py` |
| RRULE-15 | 3.3.10 | MUST | BYSETPOS MUST only be used in conjunction with another BYxxx rule part. | `rule/validation.py` |
| RRULE-16 | 3.3.10 | MUST, MUST NOT | Instances with an invalid date (e.g. February 30) MUST be ignored and MUST NOT be counted as part of the recurrence set. | `expand/expanders.py`, `expand/iterator.py` |
| RRULE-17 | 3.3.10 | normative | BYxxx parts are applied after FREQ and INTERVAL in the order BYMONTH, BYMONTHDAY, BYDAY, BYSETPOS; COUNT and UNTIL are evaluated afterwards. | `expand/iterator.py` |
| RRULE-18 | 3.3.10 | normative | Information not contained in the rule (day, month, weekday) is derived from DTSTART. | `expand/defaults.py` |
| RRULE-19 | 3.3.10 | normative | The expand/limit table: BYMONTH limits DAILY, WEEKLY, MONTHLY and expands YEARLY; BYMONTHDAY limits DAILY and expands MONTHLY, YEARLY; BYDAY limits DAILY, expands WEEKLY, and follows notes 1 and 2 for MONTHLY and YEARLY. | `expand/filters.py`, `expand/expanders.py` |
| RRULE-20 | 3.3.10 | normative | A numeric BYDAY in a YEARLY rule is an offset within the month when BYMONTH is present and within the year otherwise; in a MONTHLY rule it is an offset within the month. | `expand/expanders.py` |
| RRULE-21 | 3.3.10 | normative | WKST (default MO) defines the start of the week; it is significant for WEEKLY rules with INTERVAL > 1 and BYDAY. | `expand/periods.py` |
| RRULE-22 | 3.3.10 | normative | BYSETPOS selects the n-th occurrence within the set of instances of one interval; negative values count from the end. | `expand/setpos.py` |

## DT: date and time values (sections 3.2.19, 3.3.4, 3.3.5)

| ID | Section | Level | Requirement | Enforced in |
|---|---|---|---|---|
| DT-01 | 3.3.5 | normative | DATE-TIME has three forms: local time (floating), UTC time (suffix `Z`) and local time with a time zone reference (TZID). | `rule/parser.py`, `recurrence_set.py` |
| DT-02 | 3.3.5, 3.2.19 | MUST NOT | The TZID parameter MUST NOT be applied to DATE-TIME values specified in UTC. | `rule/validation.py` |
| DT-03 | 3.3.5 | MUST NOT | The form of date and time with a UTC offset (e.g. `19980119T230000-0800`) MUST NOT be used. | `rule/parser.py`, `rule/validation.py` |
| DT-04 | 3.2.19 | MUST NOT | The TZID parameter MUST NOT be applied to DATE values. | `rule/validation.py` |

## RSET: recurrence set (sections 3.8.5.1-3.8.5.3)

| ID | Section | Level | Requirement | Enforced in |
|---|---|---|---|---|
| RSET-01 | 3.8.5.3 | normative | The final recurrence set is all start values generated by RRULE and RDATE, excluding the values given by EXDATE. | `recurrence_set.py` |
| RSET-02 | 3.8.5.3 | normative | EXDATE takes precedence over the inclusion properties RDATE and RRULE. | `recurrence_set.py` |
| RSET-03 | 3.8.5.3 | normative | Where RRULE and RDATE generate duplicate instances, only one recurrence is considered. | `recurrence_set.py` |

## TZ: time zones (sections 3.3.5, 3.3.10, 3.8.5.3, 3.2.19)

| ID | Section | Level | Requirement | Enforced in |
|---|---|---|---|---|
| TZ-01 | 3.3.5 | normative | A local time that occurs twice (end of daylight saving time) refers to the first occurrence. | `timezones/provider.py` |
| TZ-02 | 3.3.5 | normative | An explicit local time that does not occur (start of daylight saving time) is interpreted using the UTC offset before the gap: 02:30 in a one-hour gap becomes 03:30. Applies to DTSTART, RDATE and EXDATE. | `timezones/provider.py`, `recurrence_set.py` |
| TZ-03 | 3.3.10 | MUST, MUST NOT | Instances generated by a rule with a nonexistent local time MUST be ignored and MUST NOT be counted as part of the recurrence set. | `recurrence_set.py` (through the `is_valid` hook of `expand`) |
| TZ-04 | 3.2.19 | MUST | Every TZID used MUST resolve to a time zone definition; an unknown TZID is an error (`TimeZoneError`). | `timezones/` |

## Out of scope for milestone 1

These parts of RFC 5545 are recognised by the parser but rejected as unsupported,
or are planned for later stages of the design document:

- FREQ values SECONDLY, MINUTELY, HOURLY; rule parts BYSECOND, BYMINUTE, BYHOUR
  (not implemented by design).
- BYWEEKNO, BYYEARDAY and the requirements tied to them (optional extension).
- VTIMEZONE parsing, RECURRENCE-ID, RANGE, VFREEBUSY, line folding (stages 4-7).
- Leap second `60` in UNTIL: Python `datetime` cannot represent it, so the parser
  rejects it.
