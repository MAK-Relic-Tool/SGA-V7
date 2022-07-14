from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from relic.sga import abstract
from relic.sga._core import VerificationType, Version

version = Version(7)


@dataclass
class ArchiveMetadata:
    unk_a: int
    block_size: int


@dataclass
class FileDef(abstract.FileDefABC):
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


Archive = abstract.Archive[ArchiveMetadata, FileMetadata]
Folder = abstract.Folder[FileMetadata]
File = abstract.File[FileMetadata]
Drive = abstract.Drive[FileMetadata]
