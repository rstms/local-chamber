"""Main module."""

import json
import sys
from datetime import datetime
from os import environ, execvp
from pathlib import Path
from subprocess import check_output

import yaml


def _quote(value, delims=[" "]):
    q = '"' if any(d in value for d in delims) else ""
    return f"{q}{value}{q}"


def _export(k, v):
    return f"export {k.upper()}={_quote(v)}"


def sorted_items(d):
    return {k: d[k] for k in sorted(d.keys())}.items()


def listdirs(dirs, curdir):
    if dirs is None:
        dirs = set([])
    for s in curdir.iterdir():
        if s.is_dir():
            dirs = listdirs(dirs, s)
        elif s.is_file():
            if not s.name.startswith(".") and not s.name.lower().startswith(
                "readme."
            ):
                dirs.add(curdir)
    return dirs


def _exec(cmd):
    if execvp(cmd[0], cmd):
        raise RuntimeError("subprocess failed")


def _stats(secret):
    stat = secret.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    owner = check_output(f"id -un {stat.st_uid}", shell=True).decode().strip()
    return mtime, owner


class LocalChamber:
    def __init__(self, *, secrets_dir, debug, echo):
        self.secrets_dir = secrets_dir
        self.echo = echo

    def _echo(self, msg):
        return self.echo(msg)

    def _secrets_dir(self, service):
        return self.secrets_dir / service

    def _secrets(self, service):
        secrets = self._secrets_dir(service)
        if secrets.is_dir():
            ret = {
                s.name: s.read_text().strip()
                for s in secrets.iterdir()
                if s.is_file()
            }
        else:
            ret = {}
        return ret

    def _service_name(self, service):
        return str(service.relative_to(self.secrets_dir))

    def delete(self, service, key):
        """Delete a secret, including all versions"""
        try:
            (self.secrets_dir / key).unlink()
        except Exception as ex:
            breakpoint()
            pass


    def env(self, service):
        """Print the secrets from the secrets directory in a format to export as environment variables"""
        secrets = self._secrets(service)
        self.echo("\n".join([_export(k, v) for k, v in secrets.items()]))

    def exec(self, service):
        """Executes a command with secrets loaded into the environment"""
        secrets = self._secrets(service)
        for k, v in secrets.items():
            environ[k] = v
        _exec(ctx.args)

    def export(self, output_file, fmt, service):
        """Exports parameters in the specified format"""
        secrets = self._secrets(service)
        if fmt == "json":
            out = json.dumps(secrets, sort_keys=True)
        elif fmt == "yaml":
            out = yaml.dump(secrets)
        elif fmt == "csv":
            out = "\n".join(
                [
                    f"{k},{_quote(v,[' ',','])}"
                    for k, v in sorted_items(secrets)
                ]
            )
        elif fmt == "tsv":
            out = "\n".join(
                [f"{k}\t{_quote(v)}" for k, v in sorted_items(secrets)]
            )
        elif fmt == "dotenv":
            out = "\n".join(
                [f'{k.upper()}="{v}"' for k, v in sorted_items(secrets)]
            )
        elif fmt == 'tfvars':
            out = "\n".join(
                [f'{k} = "{v}"' for k, v in sorted_items(secrets)]
            )
        else:
            raise RuntimeError(f"unknown format: {fmt}")
        output_file.write(out)

    def find(self, key, by_value):
        """Find the given secret across all services"""
        if by_value:
            self.echo("Service\tKey")
        else:
            self.echo("Service")

        services = listdirs(None, self.secrets_dir)
        for service in sorted(services):
            for secret in [s for s in service.iterdir() if s.is_file()]:
                if by_value:
                    if secret.read_text().strip() == key:
                        self.echo(
                            self._service_name(service) + "\t" + secret.name
                        )
                elif secret.name == key:
                    self.echo(self._service_name(service))

    def _import(self, service, input_file):
        "import secrets from json or yaml"
        secrets_dir = self._secrets_dir(service)
        secrets = json.load(input_file)
        for key, value in secrets.items():
            self.write(service, key, value)

    def list(self, service):
        """List the secrets set for a service"""
        secrets = {}
        for secret in [
            s for s in self._secrets_dir(service).iterdir() if s.is_file()
        ]:
            mtime, owner = _stats(secret)
            secrets[secret.name] = (1, mtime, owner)
        namelen = max(len(name) for name in secrets.keys())
        tabs = int(namelen / 8) + 1
        ltab = "\t" * tabs
        self.echo(f"Key{ltab}Version\t\tLastModified\t\tUser")
        for name in sorted(secrets.keys()):
            ltab = "\t" * (tabs - int(len(name) / 8))
            self.echo(f"{name}{ltab}1\t\t{mtime}\t{owner}")

    def list_services(self):
        """List services"""
        services = listdirs(None, self.secrets_dir)
        for service in sorted(services):
            self.echo(str(service.relative_to(self.secrets_dir)))

    def read(self, service, key):
        """Read a specific secret from the parameter store"""
        secret = self._secrets_dir(service) / key
        self.echo("Key\tValue\tVersion\tLastModified\tUser")
        mtime, owner = _stats(secret)
        self.echo(f"{secret.name}\t{secret.read_text()}\t1\t{mtime}\t{owner}")

    def write(self, service, key, value):
        """write a secret"""
        if value == "-":
            value = sys.stdin.read()
        secret = self.secrets_dir / service / key
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text(value)

    if __name__ == "__main__":
        sys.exit(cli())
