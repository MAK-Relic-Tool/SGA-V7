"""
Relic's V9.0 Specification for SGA files.

Used in 'Age of Empires 4'.
"""

from relic.sga.v9._serializers import archive_serializer as ArchiveIO
from relic.sga.v9._core import (
    Archive,
    Drive,
    Folder,
    File,
    ArchiveMetadata,
    version,
    FileMetadata,
)

__all__ = [
    "Archive",
    "Drive",
    "Folder",
    "File",
    "ArchiveIO",
    "version",
    "ArchiveMetadata",
    "FileMetadata",
]
