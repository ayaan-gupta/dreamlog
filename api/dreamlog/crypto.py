"""Application-level encryption at rest.

AES-256-GCM with a random 96-bit nonce per message. The stored blob is
``version || nonce || ciphertext+tag``. The key comes from the environment; if
none is set, a key is generated once and kept in the data directory, which is
fine for trying the app out and wrong for anything else, because the key then
sits next to the data it protects.

What this does and does not cover is written up in NOTES_FOR_README.md. In
short: transcripts, audio and pictures are encrypted. Embeddings, symbol names,
mood tags and timestamps are not, because search and the graph are computed on
them inside Postgres.
"""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSION = b"\x01"
_NONCE_BYTES = 12

KeySource = Literal["environment", "generated"]


class Cipher:
    def __init__(self, key: bytes, source: KeySource) -> None:
        if len(key) != 32:
            raise ValueError("encryption key must be 32 bytes")
        self._aead = AESGCM(key)
        self.source: KeySource = source

    def encrypt(self, plaintext: bytes, *, context: bytes = b"") -> bytes:
        """``context`` is authenticated but not stored, so a blob cannot be moved
        to a different row or path and still decrypt."""
        nonce = secrets.token_bytes(_NONCE_BYTES)
        return _VERSION + nonce + self._aead.encrypt(nonce, plaintext, context)

    def decrypt(self, blob: bytes, *, context: bytes = b"") -> bytes:
        if blob[:1] != _VERSION:
            raise ValueError("unknown ciphertext version")
        nonce, body = blob[1 : 1 + _NONCE_BYTES], blob[1 + _NONCE_BYTES :]
        return self._aead.decrypt(nonce, body, context)

    def encrypt_text(self, text: str, *, context: bytes = b"") -> bytes:
        return self.encrypt(text.encode("utf-8"), context=context)

    def decrypt_text(self, blob: bytes, *, context: bytes = b"") -> str:
        return self.decrypt(bytes(blob), context=context).decode("utf-8")


def generate_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def load_cipher(env_key: str, data_dir: Path) -> Cipher:
    if env_key:
        try:
            key = base64.urlsafe_b64decode(env_key + "=" * (-len(env_key) % 4))
        except Exception as exc:
            raise ValueError("DREAMLOG_ENCRYPTION_KEY is not valid base64") from exc
        return Cipher(key, "environment")
    path = data_dir / "dev.key"
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(generate_key())
    raw = path.read_text().strip()
    return Cipher(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), "generated")
