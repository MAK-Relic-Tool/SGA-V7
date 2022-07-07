"""
Relic's V5.0 Specification for SGA files.

Used in 'Dawn Of War II'.
"""
from relic.sga.v5._serializers import archive_serializer as ArchiveIO
from relic.sga.v5._core import (
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
