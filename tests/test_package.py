"""Tests of the package as it is installed."""

from importlib.resources import files


def test_package_is_typed() -> None:
    """The package ships its PEP 561 marker, so type checkers read its annotations."""
    assert files("pylekto").joinpath("py.typed").is_file()
