from datetime import datetime, timedelta

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from recurkit import RecurrenceSet, Rule, Series
from recurkit.ical import Event
from recurkit.series import split
from tests.stateful.naive_series import NaiveSeries, Row

DTSTART = datetime(2026, 3, 2, 9)
LENGTH = timedelta(minutes=45)
RULES = (
    "FREQ=DAILY;COUNT=12",
    "FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10",
    "FREQ=DAILY;INTERVAL=2;UNTIL=20260324T090000",
    "FREQ=MONTHLY;BYMONTHDAY=2,16,-1;COUNT=8",
)
picks = st.integers(0, 1000)


class SeriesMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.series: list[Series] = []
        self.model = NaiveSeries("s0", [], LENGTH, "")

    @initialize(text=st.sampled_from(RULES))
    def build(self, text: str) -> None:
        recurrence = RecurrenceSet(Rule.parse(text, dtstart=DTSTART))
        master = Event(
            uid="s0", start=DTSTART, length=LENGTH, summary="Class", recurrence=recurrence
        )
        self.series = [Series(master)]
        starts = [i.start for i in self.series[0].instances()]
        self.model = NaiveSeries("s0", starts, LENGTH, "Class")

    def _pick(self, index: int) -> tuple[Series, datetime]:
        ids = self.model.ids()
        rid = ids[index % len(ids)]
        owner = self.model.owner(rid)
        return next(s for s in self.series if s.uid == owner), rid

    @rule(index=picks, minutes=st.integers(-600, 600), summary=st.sampled_from(("Lab", "Exam")))
    def override(self, index: int, minutes: int, summary: str) -> None:
        series, rid = self._pick(index)
        current = series.instance(rid)
        assert current is not None
        shift = timedelta(minutes=minutes)
        series.override(rid, start=current.start + shift, summary=summary)
        self.model.override(rid, shift, summary)

    @rule(index=picks)
    def cancel(self, index: int) -> None:
        series, rid = self._pick(index)
        series.cancel(rid)
        self.model.cancel(rid)

    @rule(index=picks)
    def restore(self, index: int) -> None:
        series, rid = self._pick(index)
        series.restore(rid)
        self.model.restore(rid)

    @precondition(lambda self: len(self.series) < 4)
    @rule(index=picks)
    def cut(self, index: int) -> None:
        series, rid = self._pick(index)
        if rid == self.model.first_of(series.uid):
            return
        uid = f"s{len(self.series)}"
        head, tail = split(series, rid, uid=uid)
        self.series = [head if s is series else s for s in self.series] + [tail]
        self.model.split(rid, uid)

    @invariant()
    def same_instances_as_the_model(self) -> None:
        rows: list[Row] = sorted(
            (i.start, i.recurrence_id, i.uid, i.summary, i.cancelled)
            for s in self.series
            for i in s.instances(include_cancelled=True)
        )
        assert rows == self.model.rows()
        live = sum(1 for s in self.series for _ in s.instances())
        assert live == sum(1 for row in rows if not row[4])


TestSeriesMachine = SeriesMachine.TestCase
