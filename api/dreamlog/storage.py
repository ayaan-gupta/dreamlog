"""Object storage for audio and pictures.

``ObjectStore`` is the whole contract: put, get, delete, list, delete_all. The
default implementation writes under a local directory. An S3-compatible store
plugs in here by implementing the same five methods with boto3 or aioboto3
(``put_object``, ``get_object``, ``delete_object``, ``list_objects_v2`` with a
prefix, and a paginated ``delete_objects``); nothing above this file knows
which one it is talking to.

``EncryptedStore`` wraps any store and encrypts every object with the app key,
binding the ciphertext to its key so files cannot be swapped around on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .crypto import Cipher


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def list(self, prefix: str = "") -> list[str]: ...
    def delete_all(self) -> int: ...


class LocalDirStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"object key escapes the store: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise KeyError(key) from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list(self, prefix: str = "") -> list[str]:
        if not self.root.exists():
            return []
        keys = [p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()]
        return sorted(k for k in keys if k.startswith(prefix))

    def delete_all(self) -> int:
        keys = self.list()
        for key in keys:
            self.delete(key)
        # Leave no empty directories behind either.
        for directory in sorted((p for p in self.root.rglob("*") if p.is_dir()), reverse=True):
            directory.rmdir()
        return len(keys)


class EncryptedStore:
    def __init__(self, inner: ObjectStore, cipher: Cipher) -> None:
        self.inner = inner
        self.cipher = cipher

    def put(self, key: str, data: bytes) -> None:
        self.inner.put(key, self.cipher.encrypt(data, context=key.encode()))

    def get(self, key: str) -> bytes:
        return self.cipher.decrypt(self.inner.get(key), context=key.encode())

    def delete(self, key: str) -> None:
        self.inner.delete(key)

    def list(self, prefix: str = "") -> list[str]:
        return self.inner.list(prefix)

    def delete_all(self) -> int:
        return self.inner.delete_all()
