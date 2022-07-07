from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from relic.sga import _abc
from relic.sga._abc import FileDefABC
from relic.sga._core import VerificationType, Version

version = Version(9)


@dataclass
class ArchiveMetadata:
    sha_256: bytes
    unk_a: int
    unk_b: int
    block_size: int


@dataclass
class FileDef(FileDefABC):
    modified: datetime
    verification: VerificationType
    crc: int
    hash_pos: int


@dataclass
class FileMetadata:
    # We duplicate Models to ensure that any changes do not invalidate other versioned code
    # pylint: disable=duplicate-code
    modified: datetime
    verification: VerificationType
    crc: int
    hash_pos: int


Archive = _abc.Archive[ArchiveMetadata, FileMetadata]
Folder = _abc.Folder[FileMetadata]
File = _abc.File[FileMetadata]
Drive = _abc.Drive[FileMetadata]