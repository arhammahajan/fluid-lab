"""Tests for the public package surface."""

import fluid_lab


def test_every_declared_export_exists() -> None:
    for name in fluid_lab.__all__:
        assert getattr(fluid_lab, name) is not None, name


def test_version_is_read_from_the_installed_metadata() -> None:
    assert isinstance(fluid_lab.__version__, str)
    assert fluid_lab.__version__.count(".")


def test_version_matches_the_distribution_metadata() -> None:
    """``pyproject.toml`` is the single source of the version."""
    from importlib.metadata import version

    assert fluid_lab.__version__ == version("fluid-lab")
