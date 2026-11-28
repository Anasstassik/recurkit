from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import settings

from recurkit import parse_ics
from recurkit.ical import VTimezoneProvider
from recurkit.timezones import FakeProvider, TimeZoneProvider, ZoneInfoProvider

settings.register_profile("default", deadline=None)
settings.register_profile("ci", deadline=None, max_examples=300, print_blob=True)
settings.register_profile("quick", deadline=None, max_examples=20)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


DATA = Path(__file__).resolve().parent / "data" / "ics"


def vtimezone_provider() -> VTimezoneProvider:
    return VTimezoneProvider(parse_ics((DATA / "vtimezones.ics").read_text("utf-8")).timezones)


@dataclass(frozen=True)
class ZoneUnderTest:
    provider: TimeZoneProvider
    tzid: str


EASTERN_EUROPE = {
    "fake": ZoneUnderTest(FakeProvider(), "Fake/EasternEurope"),
    "zoneinfo": ZoneUnderTest(ZoneInfoProvider(), "Europe/Kyiv"),
    "vtimezone": ZoneUnderTest(vtimezone_provider(), "Europe/Kyiv"),
}


@pytest.fixture(params=sorted(EASTERN_EUROPE), ids=str)
def eastern_europe(request: pytest.FixtureRequest) -> ZoneUnderTest:
    return EASTERN_EUROPE[request.param]
