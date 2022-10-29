#!/usr/bin/env python3

import hvac

from .exception import ChamberError


class VaultSecrets:
    def __init__(self, base="chamber"):
        self.base = base
        self.client = hvac.Client()
        self.client.secrets.kv.default_kv_version = 2
        self.kv = self.client.secrets.kv.v2

    def _count(self, char, string):
        return len([c for c in string if c == char])

    def secrets(self, path, require_exists=True):
        try:
            list_response = self.kv.list_secrets(mount_point=self.base, path=f"/{path.strip('/')}/")
        except hvac.exceptions.InvalidPath as exc:
            if require_exists:
                raise ChamberError(f"Error: service not found: {path}") from exc
            ret = []
        else:
            ret = sorted(list_response["data"]["keys"])
        return ret

    def keys(self, path, require_exists=True):
        keys = [key for key in self.secrets(path, require_exists=False) if not key.endswith("/")]
        return sorted(keys)

    def _services(self, path):
        ret = []
        for key in self.secrets(path, require_exists=False):
            if key.endswith("/"):
                subpath = f"/{path.strip('/')}/{key}"
                sub_services = self._services(subpath)
                ret.extend(sub_services)
            else:
                ret.append(path.strip("/") + "/")
        ret = [r.strip("/") for r in ret]
        ret = [r for r in ret if len(r)]
        return sorted(list(set(ret)))

    def services(self, path):
        ret = self._services(path)
        return ret

    def delete(self, path, require_exists=True):
        self.kv.delete_metadata_and_all_versions(mount_point=self.base, path="/" + path)

    def delete_tree(self, path):
        self._walk_tree(path, self.delete)
        if path != "/":
            self.delete(path)

    def _walk_tree(self, path, func):
        levels = {}
        for service in self.services(path):
            level = self._count("/", service)
            levels.setdefault(level, [])
            levels[level].append(service)

        for level in sorted(levels.keys(), reverse=True):
            for path in levels[level]:
                for key in self.keys(path):
                    func(self._mkpath(path, key))

    def _mkpath(self, path, key):
        if path.strip("/") is None:
            _path = f"/{key}"
        else:
            _path = f"/{path.strip('/')}/{key}"
        return _path

    def set(self, path, key, value):
        _path = self._mkpath(path, key)
        secret = {key: value}
        self.kv.create_or_update_secret(mount_point=self.base, path=_path, secret=secret)

    def _get(self, path, key):
        _path = self._mkpath(path, key)
        return self.kv.read_secret_version(mount_point=self.base, path=_path)

    def get(self, path, key):
        secret = self._get(path, key)["data"]["data"]
        return secret[key]

    def get_metadata(self, path, key):
        return self._get(path, key)["data"]["metadata"]

    def load(self, path, data):
        for k, v in data.items():
            if isinstance(v, dict):
                _path = self._mkpath(path, k)
                self.load(_path, v)
            else:
                self.set(path, k, str(v))

    def _collect(self, path):
        paths = path.strip("/").split("/")
        if paths[0] == self.base:
            paths = paths[1:]
        data = self.data
        for key in paths[:-1]:
            data.setdefault(key, {})
            data = data[key]
        _path = "/".join(paths[:-1])
        key = paths[-1]
        data[key] = self.get(_path, key)

    def dump(self, path):
        self.data = {}
        self._walk_tree(path, self._collect)
        for _path in path.strip("/").split("/"):
            if _path != "":
                self.data = self.data[_path]
        return self.data
