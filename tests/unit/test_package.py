import recurkit


def test_package_exposes_version() -> None:
    assert isinstance(recurkit.__version__, str)
    assert recurkit.__version__.startswith("0.")
