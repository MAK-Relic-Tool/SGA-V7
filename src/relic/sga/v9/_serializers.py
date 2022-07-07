"""
Binary Serializers for Relic's SGA-V9
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO

from serialization_tools.structx import Struct

from relic.core.errors import MismatchError
from relic.sga._abc import (
    ArchivePtrs,
    ArchiveSerializer as ArchiveSerializerABC,
    DriveDef,
    FolderDef,
)
from relic.sga._core import StorageType, VerificationType, Version, MagicWord
from relic.sga._serializers import (
    read_toc,
    load_lazy_data,
    TocHeaderSerializer,
    FolderDefSerializer,
    DriveDefSerializer,
)
from relic.sga.errors import VersionMismatchError
from relic.sga.protocols import StreamSerializer
from relic.sga.v9._core import Archive, FileDef, FileMetadata, ArchiveMetadata, version


class FileDefSerializer(StreamSerializer[FileDef]):
    def __init__(self, layout: Struct):
        self.layout = layout

    def unpack(self, stream: BinaryIO) -> FileDef:
        (
            name_rel_pos,
            hash_pos,
            data_rel_pos,
            length,
            store_length,
            modified_seconds,
            verification_type_val,
            storage_type_val,
            crc,
        ) = self.layout.unpack_stream(stream)

        modified = datetime.fromtimestamp(modified_seconds, timezone.utc)
        storage_type: StorageType = StorageType(storage_type_val)
        verification_type: VerificationType = VerificationType(verification_type_val)
        return FileDef(
            name_pos=name_rel_pos,
            data_pos=data_rel_pos,
            length_on_disk=length,
            length_in_archive=store_length,
            storage_type=storage_type,
            modified=modified,
            verification=verification_type,
            crc=crc,
            hash_pos=hash_pos,
        )

    def pack(self, stream: BinaryIO, value: FileDef) -> int:
        modified: int = int(value.modified.timestamp())
        storage_type = value.storage_type.value  # convert enum to value
        verification_type = value.verification.value  # convert enum to value
        args = (
            value.name_pos,
            value.hash_pos,
            value.data_pos,
            value.length_on_disk,
            value.length_in_archive,
            storage_type,
            modified,
            verification_type,
            value.crc,
        )
        written: int = self.layout.pack_stream(stream, *args)
        return written


@dataclass
class ArchiveHeader:
    """
    Container for header information used by V2
    """

    name: str
    ptrs: ArchivePtrs
    sha_256: bytes


@dataclass
class ArchiveFooter:
    """Metadata that occurs after"""

    unk_a: int
    unk_b: int
    block_size: int


@dataclass
class ArchiveHeaderSerializer(StreamSerializer[ArchiveHeader]):
    """
    Serializer to convert header information to it's dataclass; ArchiveHeader
    """

    layout: Struct

    ENCODING = "utf-16-le"
    RSV_1 = 1

    def unpack(self, stream: BinaryIO) -> ArchiveHeader:
        encoded_name: bytes
        (
            encoded_name,
            header_pos,
            header_size,
            data_pos,
            data_size,
            rsv_1,
            sha_256,
        ) = self.layout.unpack_stream(stream)
        if rsv_1 != self.RSV_1:
            raise MismatchError("Reserved Field", rsv_1, self.RSV_1)

        ptrs = ArchivePtrs(header_pos, header_size, data_pos, data_size)
        name = encoded_name.rstrip(b"").decode(self.ENCODING)
        return ArchiveHeader(name, ptrs, sha_256)

    def pack(self, stream: BinaryIO, value: ArchiveHeader) -> int:
        encoded_name = value.name.encode(self.ENCODING)
        args = (
            encoded_name,
            value.ptrs.header_pos,
            value.ptrs.header_size,
            value.ptrs.data_pos,
            value.ptrs.data_size,
            self.RSV_1,
            value.sha_256,
        )

        written: int = self.layout.pack_stream(stream, *args)
        return written


@dataclass
class ArchiveFooterSerializer(StreamSerializer[ArchiveFooter]):
    """
    Reads/Writes data that occurs after the TOC portion of the Archive Header.
    """

    layout: Struct

    def unpack(self, stream: BinaryIO) -> ArchiveFooter:
        unk_a, unk_b, block_size = self.layout.unpack_stream(stream)
        return ArchiveFooter(unk_a, unk_b, block_size)

    def pack(self, stream: BinaryIO, value: ArchiveFooter) -> int:
        args = value.unk_a, value.unk_b, value.block_size
        written: int = self.layout.pack_stream(stream, *args)
        return written


def file_def2meta(file_def: FileDef) -> FileMetadata:
    """
    Extract metadata from a file definition.

    :param file_def: The file definition to extract metadata from.

    :return: Extracted metadata.
    """
    return FileMetadata(
        file_def.modified, file_def.verification, file_def.crc, file_def.hash_pos
    )


@dataclass
class ArchiveSerializer(ArchiveSerializerABC[Archive]):
    """
    Reads/Writes an Archive from/to a binary stream.
    """

    version: Version
    drive_serializer: StreamSerializer[DriveDef]
    folder_serializer: StreamSerializer[FolderDef]
    file_serializer: StreamSerializer[FileDef]
    toc_serializer: TocHeaderSerializer
    archive_header_serializer: ArchiveHeaderSerializer
    archive_footer_serializer: ArchiveFooterSerializer

    def read(
        self, stream: BinaryIO, lazy: bool = False, decompress: bool = True
    ) -> Archive:
        MagicWord.read_magic_word(stream)
        stream_version: Version = Version.unpack(stream)
        if stream_version != self.version:
            raise VersionMismatchError(stream_version, self.version)
        header = self.archive_header_serializer.unpack(stream)
        # header_pos = stream.tell()
        stream.seek(header.ptrs.header_pos)
        toc_header = self.toc_serializer.unpack(stream)
        footer = self.archive_footer_serializer.unpack(stream)
        drives, files = read_toc(
            stream=stream,
            toc_header=toc_header,
            ptrs=header.ptrs,
            drive_def=self.drive_serializer,
            file_def=self.file_serializer,
            folder_def=self.folder_serializer,
            decompress=decompress,
            build_file_meta=file_def2meta,
            name_toc_is_count=True,
        )
        # TODO perform a header check

        if not lazy:
            load_lazy_data(files)

        metadata = ArchiveMetadata(
            header.sha_256, footer.unk_a, footer.unk_b, footer.block_size
        )

        return Archive(header.name, metadata, drives)

    def write(self, stream: BinaryIO, archive: Archive) -> int:
        raise NotImplementedError


folder_layout = Struct("<5I")
folder_serializer = FolderDefSerializer(folder_layout)
drive_layout = Struct("<64s 64s 5I")
drive_serializer = DriveDefSerializer(drive_layout)
file_layout = Struct("<2I Q 3I 2B I")
file_serializer = FileDefSerializer(file_layout)
toc_layout = Struct("<8I")
toc_header_serializer = TocHeaderSerializer(toc_layout)

header_layout = Struct("<128s QIQQ I 256s")
archive_header_serializer = ArchiveHeaderSerializer(header_layout)
footer_layout = Struct("<3I")
archive_footer_serializer = ArchiveFooterSerializer(footer_layout)

archive_serializer = ArchiveSerializer(
    version=version,
    archive_header_serializer=archive_header_serializer,
    archive_footer_serializer=archive_footer_serializer,
    toc_serializer=toc_header_serializer,
    file_serializer=file_serializer,
    drive_serializer=drive_serializer,
    folder_serializer=folder_serializer,
)
