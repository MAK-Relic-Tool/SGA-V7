from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import (
    BinaryIO,
    List,
    Dict,
    Optional,
    Callable,
    Tuple,
    Iterable,
    TypeVar,
    Union,
)

from serialization_tools.size import KiB
from serialization_tools.structx import Struct

from relic.sga import _abc
from relic.sga._abc import (
    DriveDef,
    FolderDef,
    FileLazyInfo,
    TFileMeta,
    TocHeader,
    ArchivePtrs,
    File,
    Folder,
    Drive,
)
from relic.sga._core import StorageType
from relic.sga.errors import MD5MismatchError
from relic.sga.protocols import StreamSerializer, T


class TocHeaderSerializer(StreamSerializer[TocHeader]):
    def __init__(self, layout: Struct):
        self.layout = layout

    def unpack(self, stream: BinaryIO) -> TocHeader:
        (
            drive_pos,
            drive_count,
            folder_pos,
            folder_count,
            file_pos,
            file_count,
            name_pos,
            name_count,
        ) = self.layout.unpack_stream(stream)

        return TocHeader(
            (drive_pos, drive_count),
            (folder_pos, folder_count),
            (file_pos, file_count),
            (name_pos, name_count),
        )

    def pack(self, stream: BinaryIO, value: TocHeader) -> int:
        args = (
            value.drive_info[0],
            value.drive_info[1],
            value.folder_info[0],
            value.folder_info[1],
            value.file_info[0],
            value.file_info[1],
            value.name_info[0],
            value.name_info[1],
        )
        packed: int = self.layout.pack_stream(stream, *args)
        return packed


class DriveDefSerializer(StreamSerializer[DriveDef]):
    def __init__(self, layout: Struct):
        self.layout = layout

    def unpack(self, stream: BinaryIO) -> DriveDef:
        encoded_alias: bytes
        encoded_name: bytes
        (
            encoded_alias,
            encoded_name,
            folder_start,
            folder_end,
            file_start,
            file_end,
            root_folder,
        ) = self.layout.unpack_stream(stream)
        alias: str = encoded_alias.rstrip(b"\0").decode("ascii")
        name: str = encoded_name.rstrip(b"\0").decode("ascii")
        folder_range = (folder_start, folder_end)
        file_range = (file_start, file_end)
        return DriveDef(
            alias=alias,
            name=name,
            root_folder=root_folder,
            folder_range=folder_range,
            file_range=file_range,
        )

    def pack(self, stream: BinaryIO, value: DriveDef) -> int:
        alias: bytes = value.alias.encode("ascii")
        name: bytes = value.name.encode("ascii")
        args = (
            alias,
            name,
            value.folder_range[0],
            value.folder_range[1],
            value.file_range[0],
            value.file_range[1],
            value.root_folder,
        )
        packed: int = self.layout.pack_stream(stream, *args)
        return packed


class FolderDefSerializer(StreamSerializer[FolderDef]):
    def __init__(self, layout: Struct):
        self.layout = layout

    def unpack(self, stream: BinaryIO) -> FolderDef:
        (
            name_pos,
            folder_start,
            folder_end,
            file_start,
            file_end,
        ) = self.layout.unpack_stream(stream)
        folder_range = (folder_start, folder_end)
        file_range = (file_start, file_end)
        return FolderDef(
            name_pos=name_pos, folder_range=folder_range, file_range=file_range
        )

    def pack(self, stream: BinaryIO, value: FolderDef) -> int:
        args = (
            value.name_pos,
            value.folder_range[0],
            value.folder_range[1],
            value.file_range[0],
            value.file_range[1],
        )
        packed: int = self.layout.pack_stream(stream, *args)
        return packed


TFileDef = TypeVar("TFileDef", bound=_abc.FileDefABC)
BuildFileMeta = Callable[[TFileDef], TFileMeta]


def assemble_files(
    file_defs: List[TFileDef],
    names: Dict[int, str],
    data_pos: int,
    stream: BinaryIO,
    build_file_meta: BuildFileMeta[TFileDef, TFileMeta],
    decompress: bool = False,
) -> List[File[TFileMeta]]:
    files: List[File[TFileMeta]] = []
    for file_def in file_defs:
        name = names[file_def.name_pos]
        metadata: TFileMeta = build_file_meta(file_def)
        lazy_info = FileLazyInfo(
            data_pos + file_def.data_pos,
            file_def.length_in_archive,
            file_def.length_on_disk,
            stream,
            decompress,
        )
        file_compressed = file_def.storage_type != StorageType.STORE
        file = File(
            name=name,
            _data=None,
            storage_type=file_def.storage_type,
            _is_compressed=file_compressed,
            metadata=metadata,
            _lazy_info=lazy_info,
        )
        files.append(file)
    return files


def assemble_folders(
    folder_defs: List[FolderDef],
    names: Dict[int, str],
    files: List[File[TFileMeta]],
    file_offset: int = 0,
    folder_offset: int = 0,
) -> List[Folder[TFileMeta]]:
    folders: List[Folder[TFileMeta]] = []
    for folder_def in folder_defs:
        folder_name = names[folder_def.name_pos]
        sub_files = files[
            folder_def.file_range[0]
            - file_offset : folder_def.file_range[1]
            - file_offset
        ]
        folder = Folder(folder_name, [], sub_files, None)
        folders.append(folder)

    for folder_def, folder in zip(folder_defs, folders):
        folder.sub_folders = folders[
            folder_def.folder_range[0]
            - folder_offset : folder_def.folder_range[1]
            - folder_offset
        ]

    for folder in folders:
        _apply_self_as_parent(folder)

    return folders


def assemble_io_from_defs(
    drive_defs: List[DriveDef],
    folder_defs: List[FolderDef],
    file_defs: List[TFileDef],
    names: Dict[int, str],
    data_pos: int,
    stream: BinaryIO,
    build_file_meta: BuildFileMeta[TFileDef, TFileMeta],
    decompress: bool = False,
) -> Tuple[List[Drive[TFileMeta]], List[File[TFileMeta]]]:
    all_files: List[File[TFileMeta]] = []
    drives: List[Drive[TFileMeta]] = []
    for drive_def in drive_defs:
        local_file_defs = file_defs[drive_def.file_range[0] : drive_def.file_range[1]]
        local_files = assemble_files(
            local_file_defs, names, data_pos, stream, build_file_meta, decompress
        )

        local_folder_defs = folder_defs[
            drive_def.folder_range[0] : drive_def.folder_range[1]
        ]
        local_folders = assemble_folders(
            local_folder_defs,
            names,
            local_files,
            drive_def.file_range[0],
            drive_def.folder_range[0],
        )

        root_folder = (
            drive_def.root_folder - drive_def.folder_range[0]
        )  # make root folder relative to our folder slice
        drive_folder = local_folders[root_folder]
        drive = Drive(
            drive_def.alias,
            drive_def.name,
            drive_folder.sub_folders,
            drive_folder.files,
        )
        _apply_self_as_parent(drive)

        all_files.extend(local_files)
        drives.append(drive)
    return drives, all_files


def _apply_self_as_parent(
    collection: Union[Folder[TFileMeta], Drive[TFileMeta]]
) -> None:
    for folder in collection.sub_folders:
        folder.parent = collection
    for file in collection.files:
        file.parent = collection


def _unpack_helper(
    stream: BinaryIO,
    toc_info: Tuple[int, int],
    header_pos: int,
    serializer: StreamSerializer[T],
) -> List[T]:
    stream.seek(header_pos + toc_info[0])
    return [serializer.unpack(stream) for _ in range(toc_info[1])]


def read_toc_definitions(
    stream: BinaryIO,
    toc: TocHeader,
    header_pos: int,
    drive_serializer: StreamSerializer[DriveDef],
    folder_serializer: StreamSerializer[FolderDef],
    file_serializer: StreamSerializer[TFileDef],
) -> Tuple[List[DriveDef], List[FolderDef], List[TFileDef]]:
    drives = _unpack_helper(stream, toc.drive_info, header_pos, drive_serializer)
    folders = _unpack_helper(stream, toc.folder_info, header_pos, folder_serializer)
    files = _unpack_helper(stream, toc.file_info, header_pos, file_serializer)
    return drives, folders, files


def read_toc_names_as_count(
    stream: BinaryIO, toc_info: Tuple[int, int], header_pos: int, buffer_size: int = 256
) -> Dict[int, str]:
    NULL = 0
    NULL_CHAR = b"\0"
    stream.seek(header_pos + toc_info[0])

    names: Dict[int, str] = {}
    running_buffer = bytearray()
    offset = 0
    while len(names) < toc_info[1]:
        buffer = stream.read(buffer_size)
        if len(buffer) == 0:
            raise Exception("Ran out of data!")  # TODO, proper exception
        terminal_null = buffer[-1] == NULL
        parts = buffer.split(NULL_CHAR)
        if len(parts) > 1:
            parts[0] = running_buffer + parts[0]
            running_buffer.clear()
            if not terminal_null:
                running_buffer.extend(parts[-1])
            parts = parts[:-1]  # drop empty or partial

        else:
            if not terminal_null:
                running_buffer.extend(parts[0])
                offset += len(buffer)
                continue

        remaining = toc_info[1] - len(names)
        available = min(len(parts), remaining)
        for _ in range(available):
            name = parts[_]
            names[offset] = name.decode("ascii")
            offset += len(name) + 1
    return names


def _read_toc_names_as_size(
    stream: BinaryIO, toc_info: Tuple[int, int], header_pos: int
) -> Dict[int, str]:
    stream.seek(header_pos + toc_info[0])
    name_buffer = stream.read(toc_info[1])
    parts = name_buffer.split(b"\0")
    names: Dict[int, str] = {}
    offset = 0
    for part in parts:
        names[offset] = part.decode("ascii")
        offset += len(part) + 1
    return names


def _chunked_read(
    stream: BinaryIO, size: Optional[int] = None, chunk_size: Optional[int] = None
) -> Iterable[bytes]:
    if size is None and chunk_size is None:
        yield stream.read()
    elif size is None and chunk_size is not None:
        while True:
            buffer = stream.read(chunk_size)
            yield buffer
            if len(buffer) != chunk_size:
                break
    elif size is not None and chunk_size is None:
        yield stream.read(size)
    elif size is not None and chunk_size is not None:  # MyPy
        chunks = size // chunk_size
        for _ in range(chunks):
            yield stream.read(chunk_size)
        total_read = chunk_size * chunks
        if total_read < size:
            yield stream.read(size - total_read)
    else:
        raise Exception("Something impossible happened!")


@dataclass
class Md5ChecksumHelper:
    expected: Optional[bytes]
    stream: Optional[BinaryIO]
    start: int
    size: Optional[int] = None
    eigen: Optional[bytes] = None

    def read(self, stream: Optional[BinaryIO] = None) -> bytes:
        stream = self.stream if stream is None else stream
        if stream is None:
            raise IOError("No Stream Provided!")
        stream.seek(self.start)
        md5 = hashlib.md5(self.eigen) if self.eigen is not None else hashlib.md5()
        # Safer for large files to read chunked
        for chunk in _chunked_read(stream, self.size, 256 * KiB):
            md5.update(chunk)
        md5_str = md5.hexdigest()
        return bytes.fromhex(md5_str)

    def validate(self, stream: Optional[BinaryIO] = None) -> None:
        result = self.read(stream)
        if self.expected != result:
            raise MD5MismatchError(result, self.expected)


def read_toc(
    stream: BinaryIO,
    toc_header: TocHeader,
    ptrs: ArchivePtrs,
    drive_def: StreamSerializer[DriveDef],
    folder_def: StreamSerializer[FolderDef],
    file_def: StreamSerializer[TFileDef],
    decompress: bool,
    build_file_meta: BuildFileMeta[TFileDef, TFileMeta],
    name_toc_is_count: bool = True,
) -> Tuple[List[Drive[TFileMeta]], List[File[TFileMeta]]]:
    drive_defs, folder_defs, file_defs = read_toc_definitions(
        stream, toc_header, ptrs.header_pos, drive_def, folder_def, file_def
    )
    names = (
        read_toc_names_as_count(stream, toc_header.name_info, ptrs.header_pos)
        if name_toc_is_count
        else _read_toc_names_as_size(stream, toc_header.name_info, ptrs.header_pos)
    )
    drives, files = assemble_io_from_defs(
        drive_defs,
        folder_defs,
        file_defs,
        names,
        ptrs.data_pos,
        stream,
        decompress=decompress,
        build_file_meta=build_file_meta,
    )
    return drives, files


def load_lazy_data(files: List[File[TFileMeta]]) -> None:
    for file in files:
        lazy_info: Optional[FileLazyInfo] = file._lazy_info
        if lazy_info is None:
            raise Exception("API read files, but failed to create lazy info!")
        file.data = lazy_info.read()  # decompress should use cached value
        file._lazy_info = None
