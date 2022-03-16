#!/usr/bin/env python

"""Tests for `local_chamber` package."""

import pytest

from local_chamber import __version__, cli, LocalChamber 


@pytest.fixture
def chamber(shared_datadir):
    return LocalChamber(shared_datadir / 'secrets')

@pytest.fixture
def empty_chamber(shared_datadir):
    return LocalChamber(shared_datadir / 'secrets_empty')

@pytest.fixture
def json_file(shared_datadir):
    return shared_datadir/'test.json'

@pytest.fixture
def yaml_file(shared_datadir):
    return shared_datadir/'test.yaml'

def test_write_read(runner):
    result = runner.invoke(
        cli, ["-d", "write", "testservice", "key1", "value1"]
    )
    assert result.exit_code == 0, result
    result = runner.invoke(cli, ["read", "testservice", "key1"])
    assert result.exit_code == 0, result
    lines = result.output.strip().split('\n')
    assert len(lines)==2
    key, value = lines[1].split()[:2]
    assert key == 'key1'
    assert value == 'value1'


def test_delete(runner)
    result = runner.invoke('


  delete         Delete a secret, including all versions
  env            Print the secrets from the secrets directory in a format...
  exec           Executes a command with secrets loaded into the environment
  export         Exports parameters in the specified format
  find           Find the given secret across all services
  import         import secrets from json or yaml
  list           List the secrets set for a service
  list-services  List services
  read           Read a specific secret from the parameter store
  write          write a secret
