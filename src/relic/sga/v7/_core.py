from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from relic.sga import _abc
from relic.sga._core import VerificationType, Version

version = Version(7)


@dataclass
class ArchiveMetadata:
    unk_a: int
    block_size: int


@dataclass
class FileDef(_abc.FileDefABC):
    modified: datetime
    verification: VerificationType
    crc: int
    hash_pos: int


@dataclass
class FileMetadata:
    modified: datetime
    verification: VerificationType
    crc: int
    hash_pos: int


Archive = _abc.Archive[ArchiveMetadata, FileMetadata]
Folder = _abc.Folder[FileMetadata]
File = _abc.File[FileMetadata]
Drive = _abc.Drive[FileMetadata]
