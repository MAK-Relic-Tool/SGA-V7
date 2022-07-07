from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from relic.sga import _abc
from relic.sga._abc import FileDefABC
from relic.sga._core import VerificationType, Version
from relic.sga._serializers import Md5ChecksumHelper

version = Version(5)


@dataclass
class ArchiveMetadata:
    @property
    def file_md5(self) -> bytes:
        if self._file_md5.expected is None:
            raise TypeError("Md5 Checksum was not saved in metadata!")
        return self._file_md5.expected

    @property
    def header_md5(self) -> bytes:
        if self._header_md5.expected is None:
            raise TypeError("Md5 Checksum was not saved in metadata!")
        return self._header_md5.expected

    _file_md5: Md5ChecksumHelper
    _header_md5: Md5ChecksumHelper
    unk_a: int


@dataclass
class FileDef(FileDefABC):
    modified: datetime
    verification: VerificationType


@dataclass
class FileMetadata:
    modified: datetime
    verification: VerificationType


Archive = _abc.Archive[ArchiveMetadata, FileMetadata]
Folder = _abc.Folder[FileMetadata]
File = _abc.File[FileMetadata]
Drive = _abc.Drive[FileMetadata]
