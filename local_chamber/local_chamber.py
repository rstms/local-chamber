"""Main module."""

import json
import re
import sys
from datetime import datetime
from os import P_WAIT, environ, execvpe, spawnvpe
from pathlib import Path
from subprocess import check_output

import yaml

EXEC_WAIT = True


class LocalChamberError(Exception):
    pass


def _quote(value, delims=[" "], quote_char="'"):
    q = quote_char if any(d in value for d in delims) else ""
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
            if not s.name.startswith(".") and not s.name.lower().startswith("readme."):
                dirs.add(curdir)
    return dirs


def _stats(secret):
    stat = secret.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    owner = check_output(f"id -un {stat.st_uid}", shell=True).decode().strip()
    return mtime, owner


class LocalChamber:
    def __init__(self, *, secrets_dir, debug, echo):
        self.secrets_dir = Path(secrets_dir)
        self.echo = echo

    def _echo(self, msg):
        return self.echo(msg)

    def _secrets_dir(self, service):
        return self.secrets_dir / service

    def _secrets(self, service):
        secrets = self._secrets_dir(service)
        if secrets.is_dir():
            ret = {s.name: s.read_text().strip() for s in secrets.iterdir() if s.is_file()}
        else:
            ret = {}
        return ret

    def _service_name(self, service):
        return str(service.relative_to(self.secrets_dir)).lower()

    def delete(self, service, key):
        """Delete a secret, including all versions"""
        try:
            (self.secrets_dir / service.lower() / key.lower()).unlink()
        except FileNotFoundError as ex:
            raise LocalChamberError("Error: secret not found") from ex
        return 0

    def env(self, service):
        """Print the secrets from the secrets directory in a format to export as environment variables"""  # noqa
        secrets = self._secrets(service.lower())
        self.echo("\n".join([_export(k, v) for k, v in secrets.items()]))
        return 0

    def _exec(self, *, pristine, strict_value, services, cmd):
        """Executes a command with secrets loaded into the environment"""
        if not cmd:
            raise LocalChamberError(
                "Error: must specify command to run. See usage: requires at least 1 arg(s), only received 0"  # noqa
            )
        env = dict(environ).copy()
        if strict_value:
            # strict_vars must be filled from services or raise error
            strict_vars = [k for k, v in env.items() if v == strict_value]
        else:
            strict_vars = []

        if pristine:
            # do not inherit environment
            env = {}

        for service in services:
            secrets = self._secrets(service.lower())
            for k, v in secrets.items():
                env[k.upper()] = str(v)

        # if we have any strict_vars; raise exception if they have not been overwritten  # noqa
        for svar in strict_vars:
            if (svar not in env) or (env[svar] == strict_value):
                raise LocalChamberError(f"parent env was expecting {svar}={strict_value}, but was not in store")  # noqa

        if EXEC_WAIT:
            return spawnvpe(P_WAIT, cmd[0], cmd, env)
        else:
            execvpe(cmd[0], cmd, env)

    def export(self, output_file, fmt, service):
        """Exports parameters in the specified format"""
        secrets = self._secrets(service.lower())
        if fmt == "json":
            out = json.dumps(secrets, separators=[",", ":"], sort_keys=True) + "\n"
        elif fmt == "yaml":
            sorted_secrets = {k: v for k, v in sorted_items(secrets)}
            out = yaml.dump(sorted_secrets)
        elif fmt == "csv":
            out = "\n".join([f"{k},{_quote(v,[','])}" for k, v in sorted_items(secrets)]) + "\n"
        elif fmt == "tsv":
            tab = "\t"
            out = "\n".join([f"{k}\t{_quote(v,[tab])}" for k, v in sorted_items(secrets)]) + "\n"
        elif fmt == "dotenv":
            out = "\n".join([f'{k.upper()}="{v}"' for k, v in sorted_items(secrets)]) + "\n"
        elif fmt == "tfvars":
            out = "\n".join([f'{k} = "{v}"' for k, v in sorted_items(secrets)]) + "\n"
        else:
            raise RuntimeError(f"unknown format: {fmt}")
        output_file.write(out)
        return 0

    def find(self, key, by_value, regex=False):
        """Find the given secret across all services"""
        if by_value or regex:
            self.echo("Service\tKey")
        else:
            self.echo("Service")

        services = listdirs(None, self.secrets_dir)
        for service in sorted(services):
            for secret in [s for s in service.iterdir() if s.is_file()]:
                if by_value:
                    secret_text = secret.read_text().strip()
                    if regex:
                        found = re.match(key, secret_text)
                    else:
                        found = key == secret_text
                    if found:
                        self.echo(self._service_name(service) + "\t" + secret.name)
                else:
                    if regex and re.match(key, secret.name):
                        self.echo(self._service_name(service) + "\t" + secret.name)
                    elif key == secret.name:
                        self.echo(self._service_name(service))
        return 0

    def _import(self, service, input_file):
        "import secrets from json or yaml"
        secrets = json.load(input_file)
        for key, value in secrets.items():
            self.write(service, key, value)
        return 0

    def list(self, service):
        """List the secrets set for a service"""
        service = service.lower()
        secrets = {}
        for secret in [s for s in self._secrets_dir(service).iterdir() if s.is_file()]:
            mtime, owner = _stats(secret)
            secrets[secret.name] = (1, mtime, owner)
        namelen = max(len(name) for name in secrets.keys())
        tabs = int(namelen / 8) + 1
        ltab = "\t" * tabs
        self.echo(f"Key{ltab}Version\t\tLastModified\t\tUser")
        for name in sorted(secrets.keys()):
            ltab = "\t" * (tabs - int(len(name) / 8))
            self.echo(f"{name}{ltab}1\t\t{mtime}\t{owner}")
        return 0

    def list_services(self, *, service_filter=None, include_secrets=False):
        """List services"""
        self.echo("Service")
        output = []
        services = listdirs(None, self.secrets_dir)
        for service in services:
            service_name = self._service_name(service)
            if service_filter is None or service_name.startswith(str(service_filter).lower()):
                if include_secrets:
                    for secret in sorted(self._secrets(service)):
                        output.append(f"{service_name}/{secret}")
                else:
                    output.append(service_name)
        for line in sorted(output):
            self.echo(line)
        return 0

    def read(self, service, key, quiet=False):
        """Read a specific secret from the parameter store"""
        secret = self._secrets_dir(service) / key
        try:
            mtime, owner = _stats(secret)
            value = secret.read_text()
            out = f"{secret.name}\t{value}\t1\t{mtime}\t{owner}"
        except FileNotFoundError as ex:
            raise LocalChamberError("Error: Failed to read: secret not found") from ex
        if quiet:
            self.echo(value)
        else:
            self.echo("Key\tValue\tVersion\tLastModified\tUser")
            self.echo(out)

        return 0

    def write(self, service, key, value):
        """write a secret"""
        if value == "-":
            value = sys.stdin.read()
        secret = self.secrets_dir / service.lower() / key.lower()
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text(value)
        return 0
