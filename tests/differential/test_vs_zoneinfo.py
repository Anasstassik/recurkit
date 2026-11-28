from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from recurkit.timezones import FakeProvider, LocalTimeKind, ZoneInfoProvider
from tests.conftest import ZoneUnderTest, vtimezone_provider

ZONES = [
    "Europe/Kyiv",
    "America/New_York",
    "Australia/Sydney",
    "Asia/Kolkata",
    "Australia/Lord_Howe",
]
moments = st.datetimes(datetime(2000, 1, 1), datetime(2040, 12, 31))


def test_shared_transition_cases(eastern_europe: ZoneUnderTest) -> None:
    provider, tzid = eastern_europe.provider, eastern_europe.tzid
    assert provider.classify(tzid, datetime(2026, 3, 29, 3, 30)) is LocalTimeKind.GAP
    assert provider.classify(tzid, datetime(2026, 10, 25, 3, 30)) is LocalTimeKind.FOLD
    assert provider.classify(tzid, datetime(2026, 6, 1, 3, 30)) is LocalTimeKind.NORMAL
    assert provider.resolve(tzid, datetime(2026, 3, 29, 3, 0)).wall == datetime(2026, 3, 29, 4, 0)
    first = provider.resolve(tzid, datetime(2026, 10, 25, 3, 0))
    assert first.offset == timedelta(hours=3)
    assert provider.to_local(tzid, first.instant + timedelta(hours=1)) == datetime(
        2026, 10, 25, 3, 0
    )


@settings(max_examples=300)
@given(moment=moments)
def test_fake_eastern_europe_offsets_equal_kyiv(moment: datetime) -> None:
    instant = moment.replace(tzinfo=UTC)
    fake = FakeProvider().utc_offset("Fake/EasternEurope", instant)
    assert fake == ZoneInfoProvider().utc_offset("Europe/Kyiv", instant)


@settings(max_examples=300)
@given(local=moments, tzid=st.sampled_from(ZONES))
def test_resolution_matches_zoneinfo_fold_zero(local: datetime, tzid: str) -> None:
    resolved = ZoneInfoProvider().resolve(tzid, local)
    expected = local.replace(tzinfo=ZoneInfo(tzid), fold=0).astimezone(UTC)
    assert resolved.instant == expected
    assert ZoneInfoProvider().to_local(tzid, expected) == resolved.wall


VTIMEZONES = vtimezone_provider()
instants_2008_2037 = st.datetimes(datetime(2008, 1, 1), datetime(2037, 12, 31))


@settings(max_examples=300)
@given(moment=instants_2008_2037, tzid=st.sampled_from(ZONES))
def test_p9_vtimezone_offsets_equal_zoneinfo(moment: datetime, tzid: str) -> None:
    instant = moment.replace(tzinfo=UTC)
    assert VTIMEZONES.utc_offset(tzid, instant) == ZoneInfoProvider().utc_offset(tzid, instant)


@settings(max_examples=300)
@given(local=instants_2008_2037, tzid=st.sampled_from(ZONES))
def test_p9_vtimezone_gaps_and_folds_equal_zoneinfo(local: datetime, tzid: str) -> None:
    zoneinfo = ZoneInfoProvider()
    assert VTIMEZONES.classify(tzid, local) is zoneinfo.classify(tzid, local)
    assert VTIMEZONES.resolve(tzid, local) == zoneinfo.resolve(tzid, local)
