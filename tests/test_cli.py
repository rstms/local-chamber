#!/usr/bin/env python

"""Tests for `local_chamber` package."""

import pytest
from click.testing import CliRunner

from local_chamber import LocalChamberError, __version__, cli, local_chamber


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_version():
    """Test reading version and module name"""
    assert local_chamber.__name__ == "local_chamber.local_chamber"
    assert __version__
    assert isinstance(__version__, str)


def test_cli_help(runner):
    """Test the CLI."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0, result
    assert "Show this message and exit." in result.output


def test_cli_write_read(runner):
    result = runner.invoke(cli, ["-d", "write", "testservice", "key1", "value1"])
    assert result.exit_code == 0, result
    result = runner.invoke(cli, ["read", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert len(lines) == 2
    key, value = lines[1].split()[:2]
    assert key == "key1"
    assert value == "value1"


def test_cli_delete_nonexistent_key(runner):
    result = runner.invoke(cli, ["delete", "test_service", "key_not_present"])
    assert result.exit_code != 0, result
    assert isinstance(result.exception, LocalChamberError)


def test_cli_read_quiet(runner):
    result = runner.invoke(cli, ["-d", "write", "testservice", "key1", "value1"])
    assert result.exit_code == 0, result

    result = runner.invoke(cli, ["read", "-q", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert lines == ["value1"]

    result = runner.invoke(cli, ["read", "--quiet", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert lines == ["value1"]
