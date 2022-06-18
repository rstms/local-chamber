import pytest


@pytest.fixture(autouse=True)
def env_secrets_dir(monkeypatch, shared_datadir):
    secrets_dir = shared_datadir / "secrets"
    secrets_file = shared_datadir / "secrets.json"
    with monkeypatch.context() as m:
        m.setenv("SECRETS_DIR", str(secrets_dir))
        m.setenv("SECRETS_FILE", str(secrets_file))
        yield m
