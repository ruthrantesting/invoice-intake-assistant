import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class StoredBlob:
    blob_id: str
    sha256: str
    size: int
    path: Path


class LocalBlobStore:
    """Single-host immutable blob store; callers must provide a 32-byte AES key."""

    def __init__(self, root: Path, encryption_key: bytes) -> None:
        if len(encryption_key) not in {16, 24, 32}:
            raise ValueError("Blob encryption key must be a valid AES key (16, 24, or 32 bytes).")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._cipher = AESGCM(encryption_key)

    def put(self, data: bytes) -> StoredBlob:
        blob_id = uuid4().hex
        digest = hashlib.sha256(data).hexdigest()
        nonce = os.urandom(12)
        encrypted = nonce + self._cipher.encrypt(nonce, data, blob_id.encode())
        destination = self.root / blob_id
        fd, temp_name = tempfile.mkstemp(prefix=".stage-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, destination)
            dir_fd = os.open(self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return StoredBlob(blob_id, digest, len(data), destination)

    def get(self, blob_id: str, expected_sha256: str) -> bytes:
        if not blob_id.isalnum():
            raise ValueError("Invalid blob identifier.")
        path = self.root / blob_id
        encrypted = path.read_bytes()
        data = self._cipher.decrypt(encrypted[:12], encrypted[12:], blob_id.encode())
        if not hashlib.sha256(data).hexdigest() == expected_sha256:
            raise OSError("Blob integrity check failed.")
        return data

    def reconcile_orphans(
        self, referenced_blob_ids: set[str], *, delete: bool = False
    ) -> list[str]:
        """Return unreferenced immutable objects; delete only when explicitly requested."""
        orphans = sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_file()
            and path.name not in referenced_blob_ids
            and not path.name.startswith(".stage-")
        )
        if delete:
            for blob_id in orphans:
                if blob_id.isalnum():
                    (self.root / blob_id).unlink(missing_ok=True)
            directory_fd = os.open(self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return orphans
