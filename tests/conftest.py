import pytest


@pytest.fixture(autouse=True)
def env_secrets_dir(monkeypatch, shared_datadir):
    secrets_dir = shared_datadir / "secrets"
    with monkeypatch.context() as m:
        m.setenv("SECRETS_DIR", str(secrets_dir))
        yield m
