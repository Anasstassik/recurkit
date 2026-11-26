from itertools import islice

import pytest

from recurkit import RecurrenceSet, Rule
from tests.rfc_examples.data import EXAMPLES, RfcExample


def _by_freq(freq: str) -> list[RfcExample]:
    return [example for example in EXAMPLES if example.freq == freq]


def _check(example: RfcExample) -> None:
    rule = Rule.parse(example.rule, dtstart=example.start, tzid=example.tzid)
    expected = example.expected_datetimes()
    values = RecurrenceSet(rule).occurrences()
    if rule.is_infinite:
        values = islice(values, len(expected))
    assert [v.replace(tzinfo=None) for v in values] == expected  # type: ignore[call-arg]


@pytest.mark.parametrize("example", _by_freq("DAILY"), ids=lambda e: e.title)
def test_rfc_daily_examples(example: RfcExample) -> None:
    _check(example)


@pytest.mark.parametrize("example", _by_freq("WEEKLY"), ids=lambda e: e.title)
def test_rfc_weekly_examples(example: RfcExample) -> None:
    _check(example)


@pytest.mark.parametrize("example", _by_freq("MONTHLY"), ids=lambda e: e.title)
def test_rfc_monthly_examples(example: RfcExample) -> None:
    _check(example)


@pytest.mark.parametrize("example", _by_freq("YEARLY"), ids=lambda e: e.title)
def test_rfc_yearly_examples(example: RfcExample) -> None:
    _check(example)
