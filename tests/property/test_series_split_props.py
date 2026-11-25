from datetime import datetime, timedelta

from hypothesis import assume, given
from hypothesis import strategies as st

from recurkit import RecurrenceSet, Rule, Series
from recurkit.ical import Event
from recurkit.series import split
from tests.strategies import dtstarts, rule_texts

any_rule = st.sampled_from(("DAILY", "WEEKLY", "MONTHLY", "YEARLY")).flatmap(
    lambda f: rule_texts(f, set_pos=True, wkst=True)
)
HORIZON = timedelta(days=3 * 366)


counts = st.one_of(st.just(""), st.integers(2, 25).map(lambda n: f";COUNT={n}"))


@given(dtstarts, any_rule, counts, st.integers(1, 20))
def test_ser_06_ser_07_head_and_tail_together_keep_the_original_instances(
    dtstart: datetime, text: str, count: str, index: int
) -> None:
    rule = Rule.parse(text + count, dtstart=dtstart)
    master = Event(
        uid="a", start=dtstart, length=timedelta(hours=1), recurrence=RecurrenceSet(rule)
    )
    series = Series(master)
    high = dtstart + HORIZON
    original = [i.start for i in series.between(dtstart, high)]
    assume(len(original) > index)
    head, tail = split(series, original[index], uid="b")
    parts = [i.start for i in head.between(dtstart, high)]
    parts += [i.start for i in tail.between(dtstart, high)]
    assert parts == original
    assert next(tail.instances()).start == original[index]
