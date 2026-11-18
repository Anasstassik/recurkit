from itertools import islice

import pytest

from recurkit import Rule
from recurkit.expand import occurrences
from tests.rfc_examples.data import EXAMPLES, RfcExample


def _by_freq(freq: str) -> list[RfcExample]:
    return [example for example in EXAMPLES if example.freq == freq]


def _check(example: RfcExample) -> None:
    rule = Rule.parse(example.rule, dtstart=example.start, tzid=example.tzid)
    expected = example.expected_datetimes()
    if rule.is_infinite:
        assert list(islice(occurrences(rule), len(expected))) == expected
    else:
        assert list(occurrences(rule)) == expected


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
