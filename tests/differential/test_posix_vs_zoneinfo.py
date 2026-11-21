from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit.timezones import FakeProvider, PosixZone

POSIX = {
    "Europe/Kyiv": "EET-2EEST,M3.5.0/3,M10.5.0/4",
    "America/New_York": "EST5EDT,M3.2.0,M11.1.0",
    "Australia/Sydney": "AEST-10AEDT,M10.1.0,M4.1.0/3",
    "Asia/Kolkata": "IST-5:30",
    "Australia/Lord_Howe": "<+1030>-10:30<+11>-11,M10.1.0,M4.1.0",
}
PROVIDER = FakeProvider([])
ZONES: dict[str, PosixZone] = {
    zone_name: PROVIDER.add_posix(zone_name, rules) for zone_name, rules in POSIX.items()
}


@settings(max_examples=500)
@given(
    moment=st.datetimes(datetime(2008, 1, 1), datetime(2037, 12, 31)),
    tzid=st.sampled_from(sorted(POSIX)),
)
def test_posix_offsets_equal_zoneinfo(moment: datetime, tzid: str) -> None:
    instant = moment.replace(tzinfo=UTC)
    assert PROVIDER.utc_offset(tzid, instant) == instant.astimezone(ZoneInfo(tzid)).utcoffset()


def test_posix_transitions_equal_zoneinfo_every_year() -> None:
    step = timedelta(minutes=1)
    for tzid in ("Europe/Kyiv", "America/New_York", "Australia/Sydney", "Australia/Lord_Howe"):
        zone = ZoneInfo(tzid)
        for year in range(2008, 2038):
            switches = ZONES[tzid].switches(year)
            assert switches is not None
            for switch in switches:
                before = (switch - step).astimezone(zone)
                after = switch.astimezone(zone)
                assert before.utcoffset() != after.utcoffset(), (tzid, switch)
