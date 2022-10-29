#!/usr/bin/env python


"""Tests for `local_chamber` package."""

import json
import os
import pdb
import sys
from logging import getLogger
from subprocess import check_output

import click
import pytest
from click.testing import Result

from local_chamber import ChamberError, __version__, cli
from local_chamber.cli import SysArgs

# from click.testing import CliRunner


logger = getLogger()
logger.setLevel("INFO")
info = logger.info


@pytest.fixture
def runner(cli_runner):  # noqa: C901
    def _runner(cmd, **kwargs):
        if cmd[0] == "exec":
            SysArgs.set(cmd)
        elif cmd[0:2] == ["--if-exists", "exec"]:
            SysArgs.set(cmd)
        expect_exit = kwargs.pop("expect_exit", 0)
        expect_exception = kwargs.pop("expect_exception", None)
        # kwargs["catch_exceptions"] = "DEBUGGER" not in os.environ
        try:
            result = cli_runner.invoke(cli, cmd, catch_exceptions=False, **kwargs)
        except Exception as raised_exception:
            if expect_exception and isinstance(raised_exception, expect_exception):
                return Result(
                    runner=cli_runner,
                    stdout_bytes=b"",
                    stderr_bytes=b"",
                    return_value=None,
                    exit_code=-1,
                    exception=raised_exception,
                    exc_info=sys.exc_info(),
                )
            pdb.xpm()

        if result.exception:
            if expect_exception:
                assert isinstance(result.exception, expect_exception), f"{expect_exception=} != {result.exception=}"
            raise result.exception from result.exception
        elif expect_exception:
            assert result.exception, f"{expect_exception} was not raised"
        elif expect_exit is not None:
            assert result.exit_code == expect_exit

        return result

    return _runner


@pytest.fixture
def test_exec_output():
    return [
        "DYNAKEY=foo",
        "FOOKEY=foo",
        "KEY1=value1",
        "KEY_MULTIWORD=this and that",
        "TESTKEY=howdy",
    ]


@pytest.fixture
def test_env_output(test_exec_output):
    return [
        "export DYNAKEY=foo",
        "export FOOKEY=foo",
        "export KEY1=value1",
        "export KEY_MULTIWORD='this and that'",
        "export TESTKEY=howdy",
    ]


@pytest.fixture
def to_lines():
    def _to_lines(output):
        output = output.strip()
        lines = output.split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        return lines

    return _to_lines


def test_cli_version():
    """Test reading version and module name"""
    assert isinstance(cli, click.Group)
    assert __version__
    assert isinstance(__version__, str)


def test_cli_help(runner):
    """Test the CLI."""
    result = runner(["--help"])
    assert result.exit_code == 0, result
    assert "Show this message and exit." in result.output


def test_cli_write_read(runner):
    result = runner(["-d", "write", "testservice", "key1", "value1"])
    assert result.exit_code == 0, result
    result = runner(["read", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert len(lines) == 2
    key, value = lines[1].split()[:2]
    assert key == "key1"
    assert value == "value1"


def test_cli_delete_okay(runner):
    result = runner(["delete", "testservice", "key1"])
    assert result


def test_cli_delete_nonexistent_key_error(runner):
    result = runner(["delete", "testservice", "key_not_present"], expect_exception=ChamberError)
    assert result.exit_code != 0, result
    assert isinstance(result.exception, ChamberError)


def test_cli_delete_nonexistent_key_allowed_long(runner):
    result = runner(["--if-exists", "delete", "testservice", "key_not_present"])
    assert result.output == ""


def test_cli_delete_nonexistent_key_allowed_short(runner):
    result = runner(["-E", "delete", "testservice", "key_not_present"])
    assert result.output == ""


def test_cli_export(runner):

    result = runner(["export", "testservice"])
    assert result.exit_code == 0, result
    assert result.output
    testservice = json.loads(result.output)
    assert isinstance(testservice, dict)
    info(f"{testservice=}")


def test_cli_export_nonexistent_error(runner):
    result = runner(["export", "service_does_not_exist"], expect_exception=ChamberError)
    assert isinstance(result.exception, ChamberError)
    assert result.exit_code != 0, result


def test_cli_export_nonexistent_okay(runner):
    result = runner(["--if-exists", "export", "service_does_not_exist"])
    assert result.exit_code == 0, result
    assert json.loads(result.output) == {}


def test_cli_env(runner, test_env_output, to_lines):
    result = runner(["env", "testservice"], env={})
    assert result.exit_code == 0, result
    assert result.output
    result_lines = to_lines(result.output)
    assert set(result_lines) == set(test_env_output)


def test_cli_env_env_nonexistent_error(runner):
    result = runner(["env", "nonexistent_testservice"], expect_exception=ChamberError, env=dict(test="lupins"))
    assert isinstance(result.exception, ChamberError)
    assert result.exit_code != 0, result


def test_cli_env_env_nonexistent_allowed(runner, to_lines):
    result = runner(["--if-exists", "env", "nonexistent_testservice"], env=dict(test="lupins"))
    assert result.exit_code == 0, result
    assert to_lines(result.output) == []


def _verify_lines(result_lines, env_lines, test_lines):
    assert len(result_lines) + len(env_lines) + len(test_lines) - 2
    missing_lines = []
    for line in env_lines:
        if line not in result_lines:
            missing_lines.append(line)
    missing_lines = sorted(missing_lines)
    assert len(missing_lines) == 2
    assert missing_lines[0].startswith("COLUMNS=")
    assert missing_lines[1].startswith("LINES=")
    new_lines = []
    for line in result_lines:
        if line not in env_lines:
            info(line)
            new_lines.append(line)
    assert set(new_lines) == set(test_lines)


def test_cli_exec(runner, to_lines, test_exec_output):
    env_lines = to_lines(check_output("env").decode())
    result = runner(["exec", "--child", "--buffer-output", "testservice", "--", "env", "-u", "NOT_PRESENT"])
    assert result.exit_code == 0, result
    result_lines = to_lines(result.output)
    _verify_lines(result_lines, env_lines, test_exec_output)


def test_cli_exec_nonexistent_error(runner):
    result = runner(["exec", "nonexistent_testservice", "--", "env"], expect_exception=ChamberError)
    assert isinstance(result.exception, ChamberError)
    assert result.exit_code != 0, result


def test_cli_exec_nonexistent_allowed(runner, to_lines, test_exec_output):
    env_lines = to_lines(check_output("env").decode())
    result = runner(["--if-exists", "exec", "--child", "--buffer-output", "testservice", "nonexistent_testservice", "--", "env"])
    assert result.exit_code == 0, result
    result_lines = to_lines(result.output)
    _verify_lines(result_lines, env_lines, test_exec_output)


def test_cli_read_quiet(runner):
    result = runner(["-d", "write", "testservice", "key1", "value1"])
    assert result.exit_code == 0, result

    result = runner(["read", "-q", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert lines == ["value1"]

    result = runner(["read", "--quiet", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split("\n")
    assert lines == ["value1"]


def test_cli_cmd_version(runner):
    result = runner(["version"])
    assert result.exit_code == 0, result
    assert "local_chamber" in result.output


def test_cli_list_services(runner):
    result = runner(["list-services"])
    assert result.exit_code == 0, result


def test_cli_list(runner):
    result = runner(["list", "testservice"])
    assert result.exit_code == 0, result


def test_cli_backup(runner, shared_datadir):
    dest = shared_datadir / "tardis"
    dest.mkdir()
    result = runner(["backup", str(dest)])
    assert result.exit_code == 0, result
    info(result.output)

    test1 = check_output(f"ls {str(shared_datadir)}/tardis", shell=True, text=True)
    assert "_chamber.tgz" in test1

    os.chdir(str(shared_datadir))
    result = runner(["backup"])
    assert result.exit_code == 0, result
    info(result.output)

    test2 = check_output(f"ls {str(shared_datadir)}", shell=True, text=True)
    assert "_chamber.tgz" in test2

    result = runner(["backup", "-f" "daleks.tgz", str(dest)])
    assert result.exit_code == 0, result
    info(result.output)

    test3 = check_output(f"ls {str(shared_datadir)}/tardis", shell=True, text=True)
    assert "daleks.tgz" in test3

    checkdir = shared_datadir / "tardis"
    tbs = [i for i in checkdir.iterdir() if i.is_file() and i.suffix == ".tgz"]
    assert len(tbs) == 2
