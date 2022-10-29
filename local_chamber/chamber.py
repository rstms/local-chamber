"""Main module."""

import json
import re
import sys
from datetime import datetime
from os import environ, execvpe
from pathlib import Path
from subprocess import check_output, run

import hvac
import yaml

from .exception import ChamberError
from .vault import VaultSecrets

EXEC_WAIT = True


class Chamber:
    def __init__(self, *, config, debug, echo, require_exists):
        self.config = config
        secrets_dir = config["dir"]
        self.secrets_dir = Path(secrets_dir)
        self.echo = echo
        self.require_service = require_exists
        self.require_key = require_exists
        self.force_lower_services = False
        self.force_lower_keys = False

    def __enter__(self):
        return self

    def __exit__(self, _, ex, tb):
        pass

    def _secret_not_found(self, service, key):
        return f"Error: secret not found: '{service}/{key}'"

    def _service_not_found(self, service):
        return f"Error: service not found: '{service}'"

    def _echo(self, msg):
        return self.echo(msg)

    def _quote(self, value, delims=[" "], quote_char="'"):
        q = quote_char if any(d in value for d in delims) else ""
        return f"{q}{value}{q}"

    def _export(self, k, v):
        return f"export {k.upper()}={self._quote(v)}"

    def sorted_items(self, d):
        return {k: d[k] for k in sorted(d.keys())}.items()

    def delete(self, service, key):
        """Delete a secret, including all versions"""
        service, key = self._verify_key(service, key)
        if service and key:
            self._delete(service, key)
        return 0

    def _is_service(self, service):
        """return True if service exists, else False"""
        return service in self._list_services()

    def _is_secret(self, service, key):
        """return True if service exists and contains key, else False"""
        return self._is_service(service) and (key in self._secrets(service))

    def _verify_service(self, service, condition=None):
        """raise an error if require_service and condition is false"""
        if self.force_lower_services:
            service = service.lower()
        if condition is None:
            condition = self._is_service(service)
        else:
            condition = bool(condition)
        if bool(service) and condition:
            pass
        elif self.require_service:
            raise ChamberError(self._service_not_found(service))
        else:
            service = None
        return service

    def _verify_key(self, service, key, condition=None):
        """raise an error if require_service and condition is false"""
        service = self._verify_service(service)
        if service is None:
            key = None
        else:
            if self.force_lower_keys:
                key = key.lower()
            if condition is None:
                condition = self._is_secret(service, key)
            else:
                condition = bool(condition)
            if bool(key) and condition:
                pass
            elif self.require_key:
                raise ChamberError(self._secret_not_found(service, key))
            else:
                key = None
        return service, key

    def prune(self, service):
        """Prune a service, including all subkeys"""
        service = self._verify_service(service)
        if service:
            path = service.split("/")
            plen = len(path)
            for _service in self._list_services():
                _path = _service.split("/")
                if path == _path[:plen]:
                    for _key in self._secrets(_service).keys():
                        self.delete(_service, _key)
        return 0

    def env(self, service):
        """Print the secrets from the secrets directory in a format to export as environment variables"""  # noqa
        service = self._verify_service(service)
        if service:
            secrets = self._secrets(service)
            self.echo("\n".join(sorted([self._export(k, v) for k, v in secrets.items()])))
        return 0

    def _exec(self, *, services, cmd, pristine=False, strict_value='chamberme', child=True, buffer_output=True):
        """Executes a command with secrets loaded into the environment"""
        if not cmd:
            raise ChamberError("Error: must specify command to run. See usage: requires at least 1 arg(s), only received 0")  # noqa
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
            service = self._verify_service(service)
            if service:
                secrets = self._secrets(service)
                for k, v in secrets.items():
                    env[k.upper()] = str(v)

        # if we have any strict_vars; raise exception if they have not been overwritten  # noqa
        for svar in strict_vars:
            if (svar not in env) or (env[svar] == strict_value):
                raise ChamberError(f"Error: parent env was expecting {svar}={strict_value}, but was not in store")  # noqa

        self.proc = self._exec_subprocess(child, buffer_output, env, cmd)
        return self.proc.returncode

    def _exec_subprocess(self, child, buffer_output, env, cmd):
        if child:
            if buffer_output:
                proc = run(cmd, env=env, capture_output=True, text=True)
            else:
                proc = run(cmd, env=env)
            return proc
        else:
            execvpe(cmd[0], cmd, env)

    def export(self, *, output_file, fmt, service, compact_json=False, sort_keys=True):
        """Exports parameters in the specified format"""
        service = self._verify_service(service)
        if service:
            secrets = self._secrets(service)
        else:
            secrets = {}
        if fmt == "json":
            if compact_json:
                out = json.dumps(secrets, separators=[",", ":"], sort_keys=sort_keys) + "\n"
            else:
                out = json.dumps(secrets, indent=2, sort_keys=sort_keys) + "\n"
        elif fmt == "yaml":
            sorted_secrets = {k: v for k, v in self.sorted_items(secrets)}
            out = yaml.dump(sorted_secrets)
        elif fmt == "csv":
            out = "\n".join([f"{k},{self._quote(v,[','])}" for k, v in self.sorted_items(secrets)]) + "\n"
        elif fmt == "tsv":
            tab = "\t"
            out = "\n".join([f"{k}\t{self._quote(v,[tab])}" for k, v in self.sorted_items(secrets)]) + "\n"
        elif fmt == "dotenv":
            out = "\n".join([f'{k.upper()}="{v}"' for k, v in self.sorted_items(secrets)]) + "\n"
        elif fmt == "tfvars":
            out = "\n".join([f'{k} = "{v}"' for k, v in self.sorted_items(secrets)]) + "\n"
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

        if not regex:
            key = "^" + key + "$"

        services = self._list_services()

        for service in sorted(services):
            for secret_key, secret_value in self._secrets(service).items():
                if by_value:
                    if re.match(key, secret_value.strip()):
                        self.echo(service + "\t" + secret_key)
                else:
                    if re.match(key, secret_key):
                        if regex:
                            self.echo(service + "\t" + secret_key)
                        else:
                            self.echo(service)
        return 0

    def _import(self, service, input_file):
        "import secrets from json or yaml"
        secrets = json.load(input_file)
        for key, value in secrets.items():
            self.write(service, key, value)
        return 0

    def list(self, service):
        """List the secrets set for a service"""
        service = self._verify_service(service)
        if service:
            secrets = self._list(service)
        else:
            secrets = {}
        namelen = max(len(name) for name in secrets.keys())
        tabs = int(namelen / 8) + 1
        ltab = "\t" * tabs
        self.echo(f"Key{ltab}Version\t\tLastModified\t\tUser")
        for name in sorted(secrets.keys()):
            ltab = "\t" * (tabs - int(len(name) / 8))
            version, mtime, owner = secrets[name]
            self.echo(f"{name}{ltab}{version}\t\t{mtime}\t{owner}")
        return 0

    def list_services(self, *, service_filter=None, include_secrets=False):
        """List services"""
        self.echo("Service")
        output = []
        if self.force_lower_services and service_filter is not None:
            service_filter = service_filter.lower()
        services = self._list_services()
        for service in services:
            if service_filter is None or service.startswith(service_filter):
                if include_secrets:
                    for secret in sorted(self._secrets(service)):
                        output.append(f"{service}/{secret}")
                else:
                    output.append(service)
        for line in sorted(output):
            self.echo(line)
        return 0

    def read(self, service, key, quiet=False):
        """Read a specific secret from the parameter store"""
        service, key = self._verify_key(service, key)
        if key:
            value, mtime, owner = self._read(service, key)
            out = f"{key}\t{value}\t1\t{mtime}\t{owner}"
            if quiet:
                self.echo(value)
            else:
                self.echo("Key\tValue\tVersion\tLastModified\tUser")
                self.echo(out)

        return 0

    def write(self, service, key, value):
        """write a secret"""
        if self.force_lower_services:
            service = service.lower()
        if self.force_lower_keys:
            key = key.lower()
        if value == "-":
            value = sys.stdin.read()
        self._write(service, key, value)
        return 0


class VaultChamber(Chamber):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __enter__(self):
        self.secrets = VaultSecrets()
        return self

    def __exit__(self, _, ex, tb):
        pass

    def _list(self, service):
        ret = {}
        for key in self.secrets.keys(service):
            version, mtime, owner = self._metadata(service, key)
            ret[key] = (version, mtime, owner)
        return ret

    def _list_services(self):
        """return a list of available services"""
        services = self.secrets.services("/")
        return services

    def _secrets(self, service):
        keys = self.secrets.keys(service)
        return {k: self.secrets.get(service, k) for k in keys}

    def _write(self, service, key, value):
        """write a secret"""
        self.secrets.set(service, key, value)

    def _metadata(self, service, key):
        try:
            metadata = self.secrets.get_metadata(service, key)
        except hvac.exceptions.InvalidPath as ex:
            if self.require_key:
                raise ChamberError(self._secret_not_found(service, key)) from ex
            else:
                return (None, None, None)
        timestamp = metadata["created_time"].split(".")[0]
        mtime = datetime.fromisoformat(timestamp)
        owner = "undefined"
        version = metadata["version"]
        return (version, mtime, owner)

    def _read(self, service, key):
        """return a secret (value, mtime, owner)"""
        _, mtime, owner = self._metadata(service, key)
        value = self.secrets.get(service, key)
        return (value, mtime, owner)

    def _delete(self, service, key):
        """delete a secret"""
        _, _, _ = self._read(service, key)
        return self.secrets.delete(f"{service}/{key}")


class EnvdirChamber(Chamber):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secrets_dir = self.config["dir"]

    def _secrets_dir(self, service):
        return self.secrets_dir / service

    def _service_name(self, service):
        if self.force_lower_services:
            service = service.lower()
        ret = str(service.relative_to(self.secrets_dir))
        if self.force_lower_services:
            ret = ret.lower()
        return ret

    def _listdirs(self, dirs, curdir):
        if dirs is None:
            dirs = set([])
        for s in curdir.iterdir():
            if s.is_dir():
                dirs = self._listdirs(dirs, s)
            elif s.is_file():
                if not s.name.startswith(".") and not s.name.lower().startswith("readme."):
                    dirs.add(curdir)
        return dirs

    def _stats(self, secret):
        stat = secret.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        owner = check_output(f"id -un {stat.st_uid}", shell=True).decode().strip()
        return mtime, owner

    def _secrets(self, service, require_exists=True):
        """return dict of secrets in a service"""
        secrets = self._secrets_dir(service)
        if secrets.is_dir():
            ret = {s.name: s.read_text().strip() for s in secrets.iterdir() if s.is_file()}
        else:
            ret = {}
        return ret

    def _list(self, service):
        """return a list of secrets in a service"""
        secrets = {}
        for secret in [s for s in self._secrets_dir(service).iterdir() if s.is_file()]:
            mtime, owner = self._stats(secret)
            secrets[secret.name] = (1, mtime, owner)
        return secrets

    def _list_services(self):
        """return a list of available services"""
        return [self._service_name(s) for s in self._listdirs(None, self.secrets_dir)]

    def _write(self, service, key, value):
        """write a secret"""
        if self.force_lower_services:
            service = service.lower()
        if self.force_lower_keys:
            key = key.lower()
        secret = self.secrets_dir / service / key
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text(value)

    def _read(self, service, key):
        """return a secret (value, mtime, owner)"""
        secret = self._secrets_dir(service) / key
        try:
            value = secret.read_text()
            mtime, owner = self._stats(secret)
        except FileNotFoundError as ex:
            raise ChamberError(self._secret_not_found(service, key)) from ex
        return value, mtime, owner

    def _delete(self, service, key):
        """delete key from service"""
        if self.force_lower_services:
            service = service.lower()
        if self.force_lower_keys:
            key = key.lower()
        try:
            (self.secrets_dir / service / key).unlink()
        except FileNotFoundError as ex:
            raise ChamberError(self._secret_not_found(service, key)) from ex


class FileChamber(Chamber):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secrets_file = self.config["file"]
        self.dirty = False

    def __enter__(self):
        with Path(self.secrets_file).open("r") as ifp:
            self.secrets = json.load(ifp)
        self.dirty = False
        return self

    def __exit__(self, _, ex, tb):
        if self.dirty:
            with Path(self.secrets_file).open("w") as ifp:
                json.dump(self.secrets, ifp)
        self.dirty = False

    def _secrets(self, service):
        s = self.secrets
        for level in service.split("/"):
            try:
                s = s[level]
            except KeyError:
                s = {}
        ret = {k: v for k, v in s.items() if not isinstance(v, dict)}
        return ret

    def _list(self, service):
        stat = Path(self.secrets_file).stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        owner = check_output(f"id -un {stat.st_uid}", shell=True).decode().strip()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return {s: (1, mtime, owner) for s in self._secrets(service)}

    def _slist(self, secrets, path=[]):
        services = []
        for k, v in secrets.items():
            if isinstance(v, dict):
                services.append("/".join(path + [k]))
                ret = self._slist(v, path + [k])
                services.extend(ret)
        return list(set(services))

    def _list_services(self, prefix=None):
        """return a list of available services"""
        return self._slist(self.secrets, [])

    def _write(self, service, key, value):
        """write a secret"""
        s = self.secrets
        for level in service.split("/"):
            s = s.setdefault(level, {})
        s[key] = value
        self.dirty = True

    def _read(self, service, key):
        """return a secret"""
        s = self.secrets
        for level in service.split("/"):
            s = s.get(level, {})
        return s.get(key, None), None, None

    def _delete(self, service, key):
        """delete key from service"""
        s = self.secrets
        for level in service.split("/"):
            s = s.get(level, {})
        try:
            del s[key]
            self.dirty = True
        except KeyError as ex:
            raise ChamberError(self._secret_not_found(service, key)) from ex
