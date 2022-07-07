from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO, ClassVar

from serialization_tools.structx import Struct

from relic.core.errors import MismatchError
from relic.sga._abc import (
    ArchivePtrs,
    DriveDef,
    FolderDef,
    ArchiveSerializer as ArchiveSerializerABC,
)
from relic.sga._core import StorageType, VerificationType, MagicWord, Version
from relic.sga._serializers import (
    read_toc,
    load_lazy_data,
    TocHeaderSerializer,
    Md5ChecksumHelper,
    DriveDefSerializer,
    FolderDefSerializer,
)
from relic.sga.errors import VersionMismatchError
from relic.sga.protocols import StreamSerializer
from relic.sga.v5._core import FileDef, version, FileMetadata, Archive, ArchiveMetadata


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
            storage_type,
            modified,
            verification_type,
        )
        written: int = self.layout.pack_stream(stream, *args)
        return written


@dataclass
class ArchiveHeader:
    name: str
    ptrs: ArchivePtrs
    file_md5: bytes
    header_md5: bytes
    unk_a: int


@dataclass
class ArchiveHeaderSerializer(StreamSerializer[ArchiveHeader]):
    layout: Struct

    ENCODING = "utf-16-le"

    def unpack(self, stream: BinaryIO) -> ArchiveHeader:
        (
            file_md5,
            encoded_name,
            header_md5,
            header_size,
            data_pos,
            header_pos,
            rsv_1,
            rsv_0,
            unk_a,
        ) = self.layout.unpack_stream(stream)
        if (rsv_1, rsv_0) != (1, 0):
            raise MismatchError("Reserved Field", (rsv_1, rsv_0), (1, 0))

        name = encoded_name.rstrip(b"").decode(self.ENCODING)
        ptrs = ArchivePtrs(header_pos, header_size, data_pos)
        return ArchiveHeader(
            name, ptrs, file_md5=file_md5, header_md5=header_md5, unk_a=unk_a
        )

    def pack(self, stream: BinaryIO, value: ArchiveHeader) -> int:
        encoded_name = value.name.encode(self.ENCODING)
        args = (
            value.file_md5,
            encoded_name,
            value.header_md5,
            value.ptrs.header_size,
            value.ptrs.data_pos,
            value.ptrs.header_pos,
            1,
            0,
            value.unk_a,
        )
        written: int = self.layout.pack_stream(stream, *args)
        return written


def file_def2meta(f: FileDef) -> FileMetadata:
    return FileMetadata(f.modified, f.verification)


@dataclass
class ArchiveSerializer(ArchiveSerializerABC[Archive]):
    version: Version
    drive_serializer: StreamSerializer[DriveDef]
    folder_serializer: StreamSerializer[FolderDef]
    file_serializer: StreamSerializer[FileDef]
    toc_serializer: TocHeaderSerializer
    archive_header_serializer: ArchiveHeaderSerializer

    FILE_MD5_EIGEN: ClassVar = b"E01519D6-2DB7-4640-AF54-0A23319C56C3"
    HEADER_MD5_EIGEN: ClassVar = b"DFC9AF62-FC1B-4180-BC27-11CCE87D3EFF"

    def read(
        self, stream: BinaryIO, lazy: bool = False, decompress: bool = True
    ) -> Archive:
        MagicWord.read_magic_word(stream)
        version_read = Version.unpack(stream)
        if version_read != self.version:
            raise VersionMismatchError(version_read, self.version)
        header = self.archive_header_serializer.unpack(stream)

        # header_pos = stream.tell()
        stream.seek(header.ptrs.header_pos)
        toc_header = self.toc_serializer.unpack(stream)
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

        file_md5_helper = Md5ChecksumHelper(
            header.file_md5, stream, header.ptrs.header_pos, eigen=self.FILE_MD5_EIGEN
        )
        header_md5_helper = Md5ChecksumHelper(
            header.header_md5,
            stream,
            header.ptrs.header_pos,
            header.ptrs.header_size,
            eigen=self.FILE_MD5_EIGEN,
        )
        metadata = ArchiveMetadata(file_md5_helper, header_md5_helper, header.unk_a)

        return Archive(header.name, metadata, drives)

    def write(self, stream: BinaryIO, archive: Archive) -> int:
        raise NotImplementedError


folder_layout = Struct("<I 4H")
folder_serializer = FolderDefSerializer(folder_layout)

drive_layout = Struct("<64s 64s 5H")
drive_serializer = DriveDefSerializer(drive_layout)

file_layout = Struct("<5I 2B")

file_serializer = FileDefSerializer(file_layout)
toc_layout = Struct("<IH IH IH IH")
toc_header_serializer = TocHeaderSerializer(toc_layout)
header_layout = Struct("<16s 128s 16s 6I")
archive_header_serializer = ArchiveHeaderSerializer(header_layout)

archive_serializer = ArchiveSerializer(
    version=version,
    archive_header_serializer=archive_header_serializer,
    toc_serializer=toc_header_serializer,
    file_serializer=file_serializer,
    drive_serializer=drive_serializer,
    folder_serializer=folder_serializer,
)
