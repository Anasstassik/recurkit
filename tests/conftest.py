"""Shared pytest configuration: Hypothesis profiles and time zone providers."""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from hypothesis import settings

from recurkit.timezones import FakeProvider, TimeZoneProvider, ZoneInfoProvider

settings.register_profile("default", deadline=None)
settings.register_profile("ci", deadline=None, max_examples=300, print_blob=True)
settings.register_profile("quick", deadline=None, max_examples=20)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@dataclass(frozen=True)
class ZoneUnderTest:
    """The same zone as seen by one provider: a synthetic copy or the real one."""

    provider: TimeZoneProvider
    tzid: str


# Fake/EasternEurope follows the EU rules (+2/+3), like Europe/Kyiv since 1996.
EASTERN_EUROPE = {
    "fake": ZoneUnderTest(FakeProvider(), "Fake/EasternEurope"),
    "zoneinfo": ZoneUnderTest(ZoneInfoProvider(), "Europe/Kyiv"),
}


@pytest.fixture(params=sorted(EASTERN_EUROPE), ids=str)
def eastern_europe(request: pytest.FixtureRequest) -> ZoneUnderTest:
    """Runs a test once with FakeProvider and once with ZoneInfoProvider."""
    return EASTERN_EUROPE[request.param]
