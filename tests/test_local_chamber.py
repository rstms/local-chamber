#!/usr/bin/env python

"""Tests for `local_chamber` package."""

import json
import sys
from pprint import pprint
from subprocess import check_output, run

import pytest
import yaml
from yaml import Loader

from local_chamber import ChamberError, EnvdirChamber, FileChamber, VaultChamber

DEBUG = False


def _echo(msg):
    print(msg)


@pytest.fixture
def secrets(shared_datadir):
    return shared_datadir / "secrets"


@pytest.fixture
def secrets_file(shared_datadir):
    return shared_datadir / "secrets.json"


@pytest.fixture
def config(secrets, secrets_file):
    return {"dir": secrets, "file": str(secrets_file)}


@pytest.fixture
def json_file(shared_datadir):
    return shared_datadir / "test.json"


@pytest.fixture
def yaml_file(shared_datadir):
    return shared_datadir / "test.yaml"


@pytest.fixture
def testservice_json(shared_datadir):
    return shared_datadir / "testservice.json"


def _list_keys(secrets, path=[]):
    output = []
    for k, v in secrets.items():
        output.append("/".join(path + [k]))
        if isinstance(v, dict):
            output.extend(_list_keys(v, path + [k]))
    return output


@pytest.fixture
def find(shared_datadir, testinit_export):
    def _find(find_type, secrets_dir=shared_datadir / "secrets", secrets_file=shared_datadir / "secrets.json"):
        if find_type == "dir":
            output = check_output(["find", str(secrets_dir)])
            lines = output.decode().strip().split("\n")
        elif find_type == "file":
            lines = _list_keys(json.loads(secrets_file.read_text()), [])
            lines = ["/secrets/" + line for line in lines]
        elif find_type == "vault":
            json_data = testinit_export(path="/").strip()
            lines = _list_keys(json.loads(json_data), [])
            lines = ["/secrets/" + line for line in lines]
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


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_list_services(chamber_class, config, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        capsys.readouterr()
        ret = chamber.list_services()
        assert ret == 0
        captured_lines = lines(capsys)
        lines = [line for line in captured_lines if line.startswith("testservice")]
        assert lines == [
            "testservice",
            "testservice/sub1",
            "testservice/sub2",
        ]
        pprint(lines)


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_list_services_filtered(chamber_class, config, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.list_services(service_filter="testservice/sub1")
    assert ret == 0
    lines = lines(capsys)
    assert lines == ["Service", "testservice/sub1"]
    pprint(lines)


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_list_services_and_secrets(chamber_class, config, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.list_services(include_secrets=True)
    assert ret == 0
    lines = [line for line in lines(capsys) if line.startswith("testservice")]
    valid_lines = sorted(
        [
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


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_read(chamber_class, config, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.read("testservice", "key1")
    assert ret == 0
    lines = lines(capsys)
    assert len(lines) == 2
    key, value = lines[1].split()[:2]
    assert key == "key1"
    assert value == "value1"


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_readsubkey(chamber_class, config, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.read("testservice/sub2", "key1")
    assert ret == 0
    lines = lines(capsys)
    assert len(lines) == 2
    key, value = lines[1].split()[:2]
    assert key == "key1"
    assert value == "value21"


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_write(chamber_class, config, find, find_type, lines, capsys):
    before = find(find_type)
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.write("testservice", "test_write_key", "test_write_value")
    assert ret == 0
    after = find(find_type)
    assert before != after
    pprint(after)


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_delete_exists(chamber_class, config, find, find_type, lines, capsys):
    before = find(find_type)
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.delete("testservice", "key1")
    assert ret == 0
    after = find(find_type)
    assert before != after


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_delete_notfound(chamber_class, config, find, find_type, lines, capsys):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        with pytest.raises(ChamberError) as exc_info:
            chamber.delete("testservice", "sir_not_appearing_in_this_film")
    assert exc_info
    assert exc_info.type == ChamberError
    assert exc_info.value.args[0] == "Error: secret not found: 'testservice/sir_not_appearing_in_this_film'"


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_prune_exists(chamber_class, config, find, find_type, lines, capsys):
    before = find(find_type)
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.prune("testservice/sub1")
    assert ret == 0
    after = find(find_type)
    assert before != after


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_prune_notfound(chamber_class, config, find, find_type, lines, capsys):
    before = find(find_type)
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=False) as chamber:
        ret = chamber.prune("we_are_not_amused")
    assert ret == 0
    after = find(find_type)
    assert before == after


@pytest.fixture
def testservice_env_lines():
    return [
        "export DYNAKEY=foo",
        "export FOOKEY=foo",
        "export KEY1=value1",
        "export KEY_MULTIWORD='this and that'",
        "export TESTKEY=howdy",
    ]


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_env(chamber_class, config, lines, capsys, testservice_env_lines):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.env("testservice")
    assert ret == 0
    lines = lines(capsys)
    assert lines == testservice_env_lines


@pytest.fixture
def verify_json(shared_datadir):
    return (shared_datadir / "test.json").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_json(chamber_class, config, capsys, verify_json, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="json", compact_json=True, sort_keys=True, service="testservice", output_file=sys.stdout)
    assert ret == 0
    assert output(capsys) == verify_json


@pytest.fixture
def verify_yaml(shared_datadir):
    return (shared_datadir / "test.yaml").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_yaml(chamber_class, config, capsys, verify_yaml, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="yaml", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_dict = yaml.load(output(capsys), Loader=Loader)
    reference_dict = yaml.load(verify_yaml, Loader=Loader)
    assert output_dict == reference_dict


@pytest.fixture
def verify_csv(shared_datadir):
    return (shared_datadir / "test.csv").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_csv(chamber_class, config, capsys, verify_csv, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="csv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_csv = output(capsys)
    assert output_csv == verify_csv


@pytest.fixture
def verify_tsv(shared_datadir):
    return (shared_datadir / "test.tsv").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_tsv(chamber_class, config, capsys, verify_tsv, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="tsv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_tsv = output(capsys)
    assert output_tsv == verify_tsv


@pytest.fixture
def verify_dotenv(shared_datadir):
    return (shared_datadir / "test.dotenv").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_dotenv(chamber_class, config, capsys, verify_dotenv, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="dotenv", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_dotenv = output(capsys)
    assert output_dotenv == verify_dotenv


@pytest.fixture
def verify_tfvars(shared_datadir):
    return (shared_datadir / "test.tfvars").read_text()


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_export_tfvars(chamber_class, config, capsys, verify_tfvars, output):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.export(fmt="tfvars", service="testservice", output_file=sys.stdout)
    assert ret == 0
    output_tfvars = output(capsys)
    assert output_tfvars == verify_tfvars


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_list_keys(chamber_class, config, capsys, lines):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
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


@pytest.mark.parametrize("chamber_class, find_type", [(EnvdirChamber, "dir"), (FileChamber, "file"), (VaultChamber, "vault")])
def test_chamber_import(chamber_class, config, find, find_type, json_file, new_service_lines):
    before = find(find_type)
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber._import("new_service", json_file.open("r"))
    assert ret == 0
    after = find(find_type)
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


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_find(chamber_class, config, lines, capsys, valid_found_lines):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber.find(by_value=False, key="key1")
    assert ret == 0
    out_lines = lines(capsys)
    assert out_lines == valid_found_lines


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_exec(chamber_class, config, lines, capfd, testservice_json):
    before_cmd = ["env"]
    capfd.readouterr()
    proc = run(before_cmd, check=True)
    assert proc.returncode == 0
    before = lines(capfd)
    # before = proc.stdout.strip().split()

    after_cmd = ["env"]
    capfd.readouterr()
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        ret = chamber._exec(
            pristine=True,
            strict_value=None,
            services=["testservice"],
            cmd=after_cmd,
            buffer_output=False
        )
    assert ret == 0
    after = lines(capfd)

    diff = set(after).difference(set(before))
    pprint(diff)

    verify_testservice = json.loads(testservice_json.read_text())
    verify_testservice = {k.upper(): v for k, v in verify_testservice.items()}

    diff_dict = {}
    for line in diff:
        key, _, value = line.partition("=")
        diff_dict[key] = value

    assert diff_dict == verify_testservice


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_exec_bad_command(chamber_class, config):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        _cmd = ["nonexistent_command"]
        with pytest.raises(Exception) as exc_info:
            chamber._exec(pristine=True, strict_value=None, services=["testservice"], cmd=_cmd)
        print(f"Exception: {exc_info}")


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_exec_nonexistent_service(chamber_class, config):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        _cmd = ["bash", "-c", "env"]
        with pytest.raises(Exception) as exc_info:
            chamber._exec(pristine=True, strict_value=None, services=["nonexistent_service"], cmd=_cmd)
        print(f"Exception: {exc_info}")


@pytest.mark.parametrize("chamber_class", [EnvdirChamber, FileChamber, VaultChamber])
def test_chamber_exec_error_command(chamber_class, config, capfd):
    with chamber_class(config=config, debug=True, echo=_echo, require_exists=True) as chamber:
        _cmd = ["bash", "-c", "ls --nonexistent_option"]
        ret = chamber._exec(buffer_output=False, pristine=True, strict_value=None, services=["testservice"], cmd=_cmd)
    assert ret != 0, "expected non-zero return"
    out = capfd.readouterr()
    assert out.err
    print(f"stderr: {out.err}")
