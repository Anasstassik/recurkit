import importlib

import pytest

PACKAGES = ["recurkit", "recurkit.expand", "recurkit.ical", "recurkit.rule", "recurkit.timezones"]


@pytest.mark.parametrize("name", PACKAGES)
def test_exports_resolve_and_are_sorted(name: str) -> None:
    module = importlib.import_module(name)
    exported = list(module.__all__)
    assert exported == sorted(exported)
    for attribute in exported:
        assert getattr(module, attribute) is not None

