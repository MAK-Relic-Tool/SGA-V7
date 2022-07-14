from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO

from serialization_tools.structx import Struct

from relic.core.errors import MismatchError
from relic.sga.abstract import (
    ArchivePtrs,
    ArchiveSerializer as ArchiveSerializerABC,
    DriveDef,
    FolderDef,
)
from relic.sga._core import StorageType, VerificationType, MagicWord, Version
from relic.sga._serializers import (
    read_toc,
    load_lazy_data,
    TocHeaderSerializer,
    DriveDefSerializer,
    FolderDefSerializer,
)
from relic.sga.errors import VersionMismatchError
from relic.sga.protocols import StreamSerializer
from relic.sga.v7.definitions import FileDef, Archive, FileMetadata, ArchiveMetadata, version


class FileDefSerializer(StreamSerializer[FileDef]):
    def __init__(self, layout: Struct):
        self.layout = layout

    def unpack(self, stream: BinaryIO) -> FileDef:
        (
            name_rel_pos,
            data_rel_pos,
            length,
            store_length,
            modified_seconds,
            verification_type_val,
            storage_type_val,
            crc,
            hash_pos,
        ) = self.layout.unpack_stream(stream)

        modified = datetime.fromtimestamp(modified_seconds, timezone.utc)
        storage_type: StorageType = StorageType(storage_type_val)
        verification_type: VerificationType = VerificationType(verification_type_val)

        return FileDef(
            name_rel_pos,
            data_rel_pos,
            length,
            store_length,
            storage_type,
            modified,
            verification_type,
            crc,
            hash_pos,
        )

    def pack(self, stream: BinaryIO, value: FileDef) -> int:
        modified: int = int(value.modified.timestamp())
        storage_type = value.storage_type.value  # convert enum to value
        verification_type = value.verification.value  # convert enum to value
        args = (
            value.name_pos,
            value.data_pos,
            value.length_on_disk,
            value.length_in_archive,
            modified,
            verification_type,
            storage_type,
            value.crc,
            value.hash_pos,
        )
        packed: int = self.layout.pack_stream(stream, *args)
        return packed


@dataclass
class ArchiveHeader:
    name: str
    ptrs: ArchivePtrs


@dataclass
class ArchiveFooter:
    unk_a: int
    block_size: int


@dataclass
class ArchiveHeaderSerializer(StreamSerializer[ArchiveHeader]):
    layout: Struct

    ENCODING = "utf-16-le"

    def unpack(self, stream: BinaryIO) -> ArchiveHeader:
        encoded_name: bytes
        encoded_name, header_size, data_pos, rsv_1 = self.layout.unpack_stream(stream)
        if rsv_1 != 1:
            raise MismatchError("Reserved Field", rsv_1, 1)
        header_pos = stream.tell()
        ptrs = ArchivePtrs(header_pos, header_size, data_pos)
        name = encoded_name.rstrip(b"").decode(self.ENCODING)
        return ArchiveHeader(name, ptrs)

    def pack(self, stream: BinaryIO, value: ArchiveHeader) -> int:
        encoded_name = value.name.encode(self.ENCODING)
        args = encoded_name, value.ptrs.header_size, value.ptrs.data_pos, 1
        written: int = self.layout.pack_stream(stream, *args)
        return written


@dataclass
class ArchiveFooterSerializer(StreamSerializer[ArchiveFooter]):
    layout: Struct

    def unpack(self, stream: BinaryIO) -> ArchiveFooter:
        unk_a, block_size = self.layout.unpack_stream(stream)
        return ArchiveFooter(unk_a, block_size)

    def pack(self, stream: BinaryIO, value: ArchiveFooter) -> int:
        args = value.unk_a, value.block_size
        written: int = self.layout.pack_stream(stream, *args)
        return written


def file_def2meta(f: FileDef) -> FileMetadata:
    return FileMetadata(f.modified, f.verification, f.crc, f.hash_pos)


@dataclass
class ArchiveSerializer(ArchiveSerializerABC[Archive]):
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
        version_read = Version.unpack(stream)
        if version_read != self.version:
            raise VersionMismatchError(version_read, self.version)

        header = self.archive_header_serializer.unpack(stream)
        # stream.seek(header_pos)
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

        if not lazy:
            load_lazy_data(files)

        metadata = ArchiveMetadata(footer.unk_a, footer.block_size)

        return Archive(header.name, metadata, drives)

    def write(self, stream: BinaryIO, archive: Archive) -> int:
        raise NotImplementedError


folder_layout = Struct("<I 4I")
folder_serializer = FolderDefSerializer(folder_layout)
drive_layout = Struct("<64s 64s 5I")
drive_serializer = DriveDefSerializer(drive_layout)
file_layout = Struct("<5I 2B 2I")
file_serializer = FileDefSerializer(file_layout)
toc_layout = Struct("<8I")
toc_header_serializer = TocHeaderSerializer(toc_layout)
header_layout = Struct("<128s 3I")
archive_header_serializer = ArchiveHeaderSerializer(header_layout)
footer_layout = Struct("<2I")
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
