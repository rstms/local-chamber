#!/usr/bin/env python3

import tarfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory


class Restore:
    def __init__(self, *, chamber, tarball, patch, echo):
        self.chamber = chamber
        self.tarball = tarball
        self.patch = patch
        self.echo = echo

    def read(self):
        if not self.patch:
            self.echo("Deleting...")
            for service in self.chamber._list_services():
                self.echo(f"  {service}")
                for key in self.chamber._secrets(service).keys():
                    self.echo(f"    {key}")
                    self.chamber.delete(service, key)
            self.echo("Deleted.")

        self.echo("Extracting...")
        with TemporaryDirectory() as temp_dir:
            with tarfile.open(self.tarball, "r:gz") as tb:
                tb.extractall(str(temp_dir))

            restore_dir = Path(temp_dir) / self.tarball.stem

            if not restore_dir.is_dir():
                raise RuntimeError(f"{restore_dir} is not a directory")

            files = [f for f in Path(restore_dir).iterdir() if f.is_file()]
            service_count = len(files)

            self.echo("Importing extracted files...")

            for import_file in files:
                service = import_file.stem.replace(".", "/")
                self.echo(f"  {service}")
                with import_file.open("r") as fp:
                    self.chamber._import(service, fp)

        return f"Restored {service_count} services from {str(self.tarball)}"


class Backup:
    def __init__(self, *, chamber, output_path, file_name):
        self.chamber = chamber
        self.backup_label = datetime.now().strftime("%Y%m%d_%H%M%S") + "_chamber"
        if file_name:
            self.tarball_file = Path(output_path) / file_name
        else:
            self.tarball_file = Path(output_path) / (self.backup_label + ".tgz")
        self.tarball_file = self.tarball_file.resolve()

    def write(self):
        with TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / self.backup_label
            backup_dir.mkdir()
            for service in self.chamber._list_services():
                service_filename = service.replace("/", ".") + ".json"
                service_file = Path(backup_dir) / service_filename
                with service_file.open("w") as ofp:
                    self.chamber.export(output_file=ofp, fmt="json", compact_json=True, sort_keys=False, service=service)

            with tarfile.open(str(self.tarball_file), "w:gz") as tarball:
                tarball.add(backup_dir, self.backup_label)
        return str(self.tarball_file)
