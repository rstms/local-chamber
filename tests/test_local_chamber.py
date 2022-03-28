#!/usr/bin/env python

"""Tests for `local_chamber` package."""

import json
import sys
from pprint import pprint
from subprocess import check_output, run

import pytest
import yaml
from yaml import Loader

from local_chamber import LocalChamber, LocalChamberError

DEBUG = False


def _echo(msg):
    print(msg)


@pytest.fixture
def secrets(shared_datadir):
    return shared_datadir / "secrets"


@pytest.fixture
def empty_secrets(shared_datadir):
    return LocalChamber(shared_datadir / "secrets_empty")


@pytest.fixture
def chamber(secrets):
    return LocalChamber(secrets_dir=secrets, debug=DEBUG, echo=_echo)


@pytest.fixture
def json_file(shared_datadir):
    return shared_datadir / "test.json"


@pytest.fixture
def yaml_file(shared_datadir):
    return shared_datadir / "test.yaml"


@pytest.fixture
def testservice_json(shared_datadir):
    return shared_datadir / "testservice.json"


@pytest.fixture
def find(shared_datadir):
    def _find(secrets_dir=shared_datadir / "secrets"):
        output = check_output(["find", str(secrets_dir)])
        lines = output.decode().strip().split("\n")
        return lines

    yield _find


@pytest.fixture
def lines():
    def _lines(c):
        captured = c.readouterr()
        assert not captured.err
        result = captured.out
        assert result
        assert isinstance(result, str)
        lines = result.strip().split("\n")
        return lines

    yield _lines


@pytest.fixture
def output():
    def _output(capsys):
        captured = capsys.readouterr()
        assert not captured.err
        result = captured.out
        assert result
        assert isinstance(result, str)
        return result

    yield _output


@pytest.fixture
def errors():
    def _errors(capsys):
        captured = capsys.readouterr()
        assert captured.err
        assert isinstance(captured.err, str)
        lines = captured.err.strip().split("\n")
        return lines

    yield _errors


def test_chamber_list_services(chamber, lines, capsys):
    ret = chamber.list_services()
    assert ret == 0
    lines = lines(capsys)
    assert lines == [
        "Service",
        "testservice",
        "testservice/sub1",
        "testservice/sub2",
    ]
    pprint(lines)


def test_chamber_list_services_filtered(chamber, lines, capsys):
    ret = chamber.list_services(service_filter="testservice/sub1")
    assert ret == 0
    lines = lines(capsys)
    assert lines == ["Service", "testservice/sub1"]
    pprint(lines)


def test_chamber_list_services_and_secrets(chamber, lines, capsys):
    ret = chamber.list_services(include_secrets=True)
    assert ret == 0
    lines = lines(capsys)
    valid_lines = sorted(
        [
            "Service",
            "testservice/dynakey",
            "testservice/key1",
            "testservice/key_multiword",
            "testservice/fookey",
            "testservice/testkey",
            "testservice/sub1/key2",
            "testservice/sub1/key1",
            "testservice/sub2/key2",
            "testservice/sub2/key1",
        ]
    )
    assert lines == valid_lines


def test_chamber_read(chamber, lines, capsys):
    ret = chamber.read("testservice", "key1")
    assert ret == 0
    lines = lines(capsys)
    assert len(lines) == 2
    key, value = lines[1].split()[:2]
    assert key == "key1"
    assert value == "value1"


def test_chamber_write(chamber, find, lines, capsys):
    before = find()
    ret = chamber.write("testservice", "test_write_key", "test_write_value")
    assert ret == 0
    after = find()
    assert before != after
    pprint(after)


def test_chamber_delete_exists(chamber, find, lines, capsys):
    before = find()
    ret = chamber.delete("testservice", "key1")
    assert ret == 0
    after = find()
    assert before != after


def test_chamber_delete_notfound(chamber, find, lines, capsys):
    with pytest.raises(LocalChamberError) as exc_info:
        chamber.delete("testservice", "sir_not_appearing_in_this_film")
    assert exc_info
    assert exc_info.type == LocalChamberError
    assert exc_info.value.args[0] == "Error: secret not found"


@pytest.fixture
def testservice_env_lines():
    return [
        "export DYNAKEY=foo",
        "export KEY1=value1",
        "export KEY_MULTIWORD='this and that'",
        "export FOOKEY=foo",
        "export TESTKEY=howdy",
    ]


def test_chamber_env(chamber, lines, capsys, testservice_env_lines):
    ret = chamber.env("testservice")
    assert ret == 0
    lines = lines(capsys)
    assert lines == testservice_env_lines


@pytest.fixture
def verify_json(shared_datadir):
    return (shared_datadir / "test.json").read_text()


def test_chamber_export_json(chamber, capsys, verify_json, output):
    ret = chamber.export(fmt="json", service="testservice", output_file=sys.stdout)
    assert ret == 0
    assert output(capsys) == verify_json


@pytest.fixture
def verify_yaml(shared_datadir):
    return (shared_datadir / "test.yaml").read_text()


def test_chamber_export_yaml(chamber, capsys, verify_yaml, output):
    ret = chamber.export(fmt="yaml", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_dict = yaml.load(output(capsys), Loader=Loader)
    reference_dict = yaml.load(verify_yaml, Loader=Loader)
    assert output_dict == reference_dict


@pytest.fixture
def verify_csv(shared_datadir):
    return (shared_datadir / "test.csv").read_text()


def test_chamber_export_csv(chamber, capsys, verify_csv, output):
    ret = chamber.export(fmt="csv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_csv = output(capsys)
    assert output_csv == verify_csv


@pytest.fixture
def verify_tsv(shared_datadir):
    return (shared_datadir / "test.tsv").read_text()


def test_chamber_export_tsv(chamber, capsys, verify_tsv, output):
    ret = chamber.export(fmt="tsv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_tsv = output(capsys)
    assert output_tsv == verify_tsv


@pytest.fixture
def verify_dotenv(shared_datadir):
    return (shared_datadir / "test.dotenv").read_text()


def test_chamber_export_dotenv(chamber, capsys, verify_dotenv, output):
    ret = chamber.export(fmt="dotenv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_dotenv = output(capsys)
    assert output_dotenv == verify_dotenv


@pytest.fixture
def verify_tfvars(shared_datadir):
    return (shared_datadir / "test.tfvars").read_text()


def test_chamber_export_tfvars(chamber, capsys, verify_tfvars, output):
    ret = chamber.export(fmt="tfvars", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_tfvars = output(capsys)
    assert output_tfvars == verify_tfvars


def test_chamber_list_keys(chamber, capsys, lines):
    ret = chamber.list("testservice/sub2")
    assert ret == 0
    output_lines = lines(capsys)
    assert len(output_lines) == 3
    fields = []
    for line in output_lines:
        fields.append(line.split()[0])
    assert fields == ["Key", "key1", "key2"]


@pytest.fixture
def new_service_lines():
    return [
        "/secrets/new_service",
        "/secrets/new_service/dynakey",
        "/secrets/new_service/fookey",
        "/secrets/new_service/key1",
        "/secrets/new_service/key_multiword",
        "/secrets/new_service/testkey",
    ]


def test_chamber_import(chamber, find, json_file, new_service_lines):
    before = find()
    ret = chamber._import("new_service", json_file.open("r"))
    assert ret == 0
    after = find()
    assert before != after
    new_lines = set(after).difference(set(before))
    assert len(new_lines) == 6
    validate_lines = sorted(new_service_lines)
    new_lines = sorted(new_lines)
    for i, line in enumerate(new_lines):
        assert line.endswith(validate_lines[i])


@pytest.fixture
def valid_found_lines():
    return ["Service", "testservice", "testservice/sub1", "testservice/sub2"]


def test_chamber_find(chamber, lines, capsys, valid_found_lines):
    ret = chamber.find(by_value=False, key="key1")
    assert ret == 0
    out_lines = lines(capsys)
    assert out_lines == valid_found_lines


def test_chamber_exec(chamber, lines, capfd, testservice_json):
    before_cmd = ["env"]
    capfd.readouterr()
    proc = run(before_cmd, check=True)
    assert proc.returncode == 0
    before = lines(capfd)
    # before = proc.stdout.strip().split()

    after_cmd = ["env"]
    capfd.readouterr()
    ret = chamber._exec(
        pristine=True,
        strict_value=None,
        services=["testservice"],
        cmd=after_cmd,
    )
    assert ret == 0
    after = lines(capfd)

    diff = set(after).difference(set(before))
    pprint(diff)

    verify_testservice = json.loads(testservice_json.read_text())
    verify_testservice = {k: v for k, v in verify_testservice.items()}

    diff_dict = {}
    for line in diff:
        key, _, value = line.partition("=")
        diff_dict[key.lower()] = value

    assert diff_dict == verify_testservice


def test_exec_bad_command(chamber):
    _cmd = ["nonexistent_command"]
    with pytest.raises(Exception) as exc_info:
        chamber._exec(pristine=True, strict_value=None, services=["testservice"], cmd=_cmd)
    print(f"Exception: {exc_info}")


def test_exec_error_command(chamber, capfd):
    _cmd = ["bash", "-c", "ls --nonexistent_option"]
    ret = chamber._exec(pristine=True, strict_value=None, services=["testservice"], cmd=_cmd)
    assert ret != 0, "expected non-zero return"
    out = capfd.readouterr()
    assert out.err
    print(f"stderr: {out.err}")
