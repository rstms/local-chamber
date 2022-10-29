import logging
import tempfile
from pathlib import Path

import pytest

from local_chamber.archive import Backup, Restore
from local_chamber.chamber import VaultChamber

logger = logging.getLogger()
logger.setLevel("INFO")
info = logger.info


@pytest.fixture
def config(shared_datadir):
    return {"dir": shared_datadir / "secrets", "file": shared_datadir / "secrets.json"}


@pytest.fixture
def chamber(config):
    with VaultChamber(config=config, debug=True, echo=info, require_exists=True) as c:
        yield c


def test_archive_init(chamber):
    services = chamber._list_services()
    info(f"type(services) == {type(services)}")
    assert isinstance(services, list)


def test_archive_export(chamber):
    with tempfile.NamedTemporaryFile("w+") as buf:
        chamber.export(output_file=buf, fmt="json", service="testservice", compact_json=False, sort_keys=False)
        buf.seek(0)
        for line in buf.readlines():
            info(line)


def test_backup_restore(chamber, shared_datadir):
    reference = {}
    for service in chamber._list_services():
        reference[service] = chamber._secrets(service)

    archive_dir = shared_datadir / "archives"
    archive_dir.mkdir()
    before_items = [i for i in archive_dir.iterdir()]
    b = Backup(chamber=chamber, output_path=archive_dir, file_name=None)
    info(b)
    result = b.write()
    tarball = Path(result)
    assert tarball.is_file()
    assert tarball.suffix == ".tgz"
    info(result)
    after_items = [i for i in archive_dir.iterdir()]
    assert before_items != after_items
    info(repr(after_items))

    for service in chamber._list_services():
        if service == "docker/credentials/secret":
            breakpoint()
        for key in chamber._secrets(service).keys():
            chamber.delete(service, key)

    services = chamber._list_services()
    assert len(services) == 0

    r = Restore(chamber=chamber, tarball=tarball, patch=False, echo=info)
    result = r.read()
    info(f"read returned: {result}")

    restored = {}
    for service in chamber._list_services():
        restored[service] = chamber._secrets(service)

    assert restored == reference
