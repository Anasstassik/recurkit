# Milestone 1: results

Milestone 1 covers calendar arithmetic, the rule model and parser, the date
generator, recurrence sets with time zones, and the recurrence properties of
iCalendar text. This page records the numbers it was accepted with.

## Code size (pygount)

`pygount --format=summary recurkit` counts code lines. The library code
carries no comments or docstrings.

| Part | Code lines |
|---|---:|
| `calendar_math.py` | 212 |
| `errors.py` | 32 |
| `rule/` (model, parser, validation, describe) | 514 |
| `expand/` (defaults, periods, filters, expanders, setpos, iterator, query, jump) | 568 |
| `recurrence_set.py` | 150 |
| `timezones/` (provider, fake, POSIX, zoneinfo adapter) | 301 |
| `ical/` (content lines, recurrence properties, writer) | 262 |
| `__init__.py` files with exports | 13 |
| **Total** | **2052** |

The target was at least 2000 code lines.

## Tests

| Directory | Test functions | What they check |
|---|---:|---|
| `tests/unit` | 132 | each module; requirement IDs in test names |
| `tests/property` | 14 | properties P1 to P8 against a naive day-by-day oracle |
| `tests/differential` | 11 | `dateutil.rrule` and `zoneinfo` as references |
| `tests/rfc_examples` | 6 | 37 RRULE examples and the RDATE/EXDATE examples of RFC 5545 |
| `tests/perf` | 3 | memory of lazy iteration, periods expanded by window queries |
| **Total** | **166** | 332 test cases after parametrization |

The target was at least 40 test functions. Every requirement ID of
[requirements.md](requirements.md) appears in a test name, which
`tests/unit/test_requirement_ids.py` enforces.

## Coverage

`pytest -q --cov` with branch coverage:

| Statements | Missed | Branches | Partial | Coverage |
|---:|---:|---:|---:|---:|
| 1804 | 25 | 636 | 31 | 98% |

CI fails below 90% (`fail_under` in `pyproject.toml`).

## Static checks

- `ruff check .` and `mypy --strict` (`mypy recurkit`): no findings.
- `lint-imports`: three contracts kept (layers `ical -> recurrence_set ->
  expand -> rule -> calendar_math`; expansion without time zones; `zoneinfo`
  only in the adapter).

## Environment

Python 3.12.3, pygount 3.2.0, pytest 9.2.0, coverage 7.17.4, Hypothesis
6.170.17, python-dateutil 4.0.0, ruff 0.17.6, mypy 2.4.1.

## Beyond the plan

BYWEEKNO and BYYEARDAY (D-07), parsing and writing of DTSTART, RRULE, RDATE
and EXDATE lines (D-08), synthetic zones from POSIX TZ strings and plain
English rule descriptions were added in this milestone. Components (VEVENT),
DURATION and the command-line tool remain in stage 4.
