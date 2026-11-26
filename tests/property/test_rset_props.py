from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import islice, pairwise

from hypothesis import given
from hypothesis import strategies as st

from recurkit import RecurrenceSet, Rule
from recurkit.expand import occurrences
from recurkit.timezones import FakeProvider
from tests.strategies import FAKE_ZONES, dtstarts, explicit_datetimes, rule_texts

FAKE = FakeProvider()
any_rule = st.sampled_from(("DAILY", "WEEKLY", "MONTHLY", "YEARLY")).flatmap(
    lambda f: rule_texts(f, set_pos=True, wkst=True)
)
HORIZON = timedelta(days=200)


@st.composite
def floating_sets(draw: st.DrawFn) -> tuple[Rule, list[datetime], list[datetime]]:
    dtstart = draw(dtstarts)
    rule = Rule.parse(draw(any_rule), dtstart=dtstart)
    generated = list(islice(occurrences(rule, until=dtstart + HORIZON), 30))
    rdates, exdates = draw(explicit_datetimes(dtstart)), draw(explicit_datetimes(dtstart))
    if generated:
        rdates += draw(st.lists(st.sampled_from(generated), max_size=3))
        exdates += draw(st.lists(st.sampled_from(generated), max_size=3))
    return rule, rdates, exdates


@given(case=floating_sets())
def test_p6_set_is_rule_minus_exdate_plus_rdate(
    case: tuple[Rule, list[datetime], list[datetime]],
) -> None:
    rule, rdates, exdates = case
    start = rule.require_dtstart()
    assert isinstance(start, datetime)
    end = start + HORIZON
    actual = list(RecurrenceSet(rule, rdates=rdates, exdates=exdates).between(start, end))
    generated = set(occurrences(rule, until=end))
    expected = sorted((generated | {d for d in rdates if start <= d <= end}) - set(exdates))
    assert actual == expected
    assert len(actual) == len(set(actual))


@given(text=any_rule, dtstart=dtstarts, tzid=st.sampled_from(FAKE_ZONES))
def test_p8_local_time_is_kept_and_instants_increase(
    text: str, dtstart: datetime, tzid: str
) -> None:
    rule = Rule.parse(text, dtstart=dtstart, tzid=tzid)
    end = dtstart + HORIZON
    instances = list(RecurrenceSet(rule, provider=FAKE).between(dtstart, end))
    generated = set(occurrences(replace(rule, tzid=None), until=end + timedelta(days=1)))
    for value in instances:
        assert isinstance(value, datetime)
        local = value.replace(tzinfo=None)
        if local != dtstart:
            assert local in generated
            assert FAKE.to_local(tzid, value) == local
    instants = [v.astimezone(UTC) for v in instances if isinstance(v, datetime)]
    assert all(a < b for a, b in pairwise(instants))
