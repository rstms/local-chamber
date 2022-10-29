import json
import logging

import pytest

from local_chamber import VaultSecrets

logging.getLogger("urllib3.connectionpool").setLevel("WARNING")


@pytest.fixture(autouse=True)
def env_secrets_dir(monkeypatch, shared_datadir):
    secrets_dir = shared_datadir / "secrets"
    secrets_file = shared_datadir / "secrets.json"
    with monkeypatch.context() as m:
        m.setenv("SECRETS_DIR", str(secrets_dir))
        m.setenv("SECRETS_FILE", str(secrets_file))
        yield m


@pytest.fixture
def testinit_export():
    def _testinit_export(path="/"):
        secrets = VaultSecrets("chamber")
        data = secrets.dump(path)
        ret = json.dumps(data, indent=2) + "\n"
        return ret

    yield _testinit_export


@pytest.fixture
def testinit_clear():
    def _testinit_clear(path="/"):
        secrets = VaultSecrets("chamber")
        secrets.delete_tree(path)

    yield _testinit_clear


@pytest.fixture
def testinit_import():
    def _testinit_import(path="/", json_string="{}"):
        secrets = VaultSecrets("chamber")
        data = json.loads(json_string)
        secrets.load(path, data)

    yield _testinit_import


@pytest.fixture
def reset_vault(shared_datadir, testinit_clear, testinit_import):
    def _reset_vault():
        datafile = shared_datadir / "secrets.json"
        testinit_clear(path="testservice")
        testinit_clear(path="new_service")
        testinit_import(path="/", json_string=datafile.read_text())

    return _reset_vault


@pytest.fixture(scope="function", autouse=True)
def init_vault(reset_vault):
    reset_vault()
