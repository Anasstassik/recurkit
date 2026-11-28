from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from itertools import islice, pairwise, takewhile

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit import RecurrenceSet, Rule
from recurkit.expand import Occurrence, occurrences
from recurkit.recurrence_set import ValueKind
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


SERIES_KINDS = st.sampled_from(("all-day", "floating", "utc", "zoned"))
OFFSETS = st.integers(-12 * 4, 14 * 4).map(lambda q: timezone(timedelta(minutes=15 * q)))


@st.composite
def sets_of_every_kind(draw: st.DrawFn) -> RecurrenceSet:
    kind, start = draw(SERIES_KINDS), draw(dtstarts)
    explicit = draw(explicit_datetimes(start)) + draw(explicit_datetimes(start))
    split = draw(st.integers(0, len(explicit)))
    if kind == "all-day":
        rule = Rule.parse(draw(any_rule), dtstart=start.date())
        values: list[Occurrence] = [v.date() for v in explicit]
    elif kind == "floating":
        rule = Rule.parse(draw(any_rule), dtstart=start)
        values = list(explicit)
    else:
        aware = start.replace(tzinfo=UTC) if kind == "utc" else start
        tzid = draw(st.sampled_from(FAKE_ZONES)) if kind == "zoned" else None
        rule = Rule.parse(draw(any_rule), dtstart=aware, tzid=tzid)
        forms = st.one_of(st.just(None), OFFSETS) if kind == "zoned" else OFFSETS
        values = [v.replace(tzinfo=draw(forms)) for v in explicit]
    return RecurrenceSet(rule, rdates=values[:split], exdates=values[split:], provider=FAKE)


@given(rset=sets_of_every_kind())
def test_pp3_every_value_has_the_kind_of_dtstart(rset: RecurrenceSet) -> None:
    start = rset.rule.require_dtstart()
    end = start + HORIZON
    for value in rset.between(start, end):
        assert rset.kind.accepts(value)
        if rset.kind is ValueKind.UTC:
            assert isinstance(value, datetime) and value.utcoffset() == timedelta(0)
        if rset.kind is ValueKind.ZONED:
            assert isinstance(value, datetime) and value.tzname() == rset.tzid
            assert rset.frame is not None
            assert rset.frame.to_local(value) == value.replace(tzinfo=None)


@settings(max_examples=100, deadline=None)
@given(
    text=st.sampled_from(("HOURLY", "MINUTELY")).flatmap(lambda f: rule_texts(f, set_pos=True)),
    tzid=st.sampled_from(FAKE_ZONES),
    day=st.integers(0, 365),
    hours=st.integers(0, 30),
)
def test_pp1_zoned_sub_daily_queries_equal_a_walk(
    text: str, tzid: str, day: int, hours: int
) -> None:
    dtstart = datetime(2026, 1, 1, 0, 30) + timedelta(days=day)
    rset = RecurrenceSet(Rule.parse(text, dtstart=dtstart, tzid=tzid), provider=FAKE)
    low = datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=day)
    high = low + timedelta(hours=hours)
    walk = list(takewhile(lambda v: v <= high, rset._values(None, high)))  # type: ignore[operator]
    inside = [v for v in walk if low <= v <= high]  # type: ignore[operator]
    assert list(rset.between(low, high)) == inside
    following = next((v for v in walk if v > low), None)  # type: ignore[operator]
    if following is not None:
        assert rset.after(low) == following
    below = [v for v in walk if v < high]  # type: ignore[operator]
    assert rset.before(high) == (below[-1] if below else None)
