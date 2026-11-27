from __future__ import annotations

from recurkit.ical import Calendar
from recurkit.series.series import Series


def load_series(calendar: Calendar) -> dict[str, Series]:
    return {event.uid: Series.from_event(event) for event in calendar if not event.is_override}
