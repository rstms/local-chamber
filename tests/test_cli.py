#!/usr/bin/env python

"""Tests for `local_chamber` package."""

import os
from logging import getLogger
from subprocess import check_output

import click
import pytest
from click.testing import CliRunner

from local_chamber import ChamberError, __version__, cli

logger = getLogger()
logger.setLevel("INFO")
info = logger.info


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_version():
    """Test reading version and module name"""
    assert isinstance(cli, click.Group)
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
    assert isinstance(result.exception, ChamberError)


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


def test_cli_cmd_version(runner):
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0, result
    assert "local_chamber" in result.output


def test_cli_list_services(runner):
    result = runner.invoke(cli, ["list-services"])
    assert result.exit_code == 0, result


def test_cli_list(runner):
    result = runner.invoke(cli, ["list", "testservice"])
    assert result.exit_code == 0, result


def test_cli_backup(runner, shared_datadir):
    dest = shared_datadir / "tardis"
    dest.mkdir()
    result = runner.invoke(cli, ["backup", str(dest)])
    assert result.exit_code == 0, result
    info(result.output)

    test1 = check_output(f"ls {str(shared_datadir)}/tardis", shell=True, text=True)
    assert "_chamber.tgz" in test1

    os.chdir(str(shared_datadir))
    result = runner.invoke(cli, ["backup"])
    assert result.exit_code == 0, result
    info(result.output)

    test2 = check_output(f"ls {str(shared_datadir)}", shell=True, text=True)
    assert "_chamber.tgz" in test2

    result = runner.invoke(cli, ["backup", "-f" "daleks.tgz", str(dest)])
    assert result.exit_code == 0, result
    info(result.output)

    test3 = check_output(f"ls {str(shared_datadir)}/tardis", shell=True, text=True)
    assert "daleks.tgz" in test3

    checkdir = shared_datadir / "tardis"
    tbs = [i for i in checkdir.iterdir() if i.is_file() and i.suffix == ".tgz"]
    assert len(tbs) == 2
