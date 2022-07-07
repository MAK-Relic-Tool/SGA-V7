from typing import Optional, List, BinaryIO, Union, Sequence

from relic.sga import StorageType
from relic.sga._serializers import Md5ChecksumHelper
from relic.sga.v2 import File, ArchiveMetadata, Folder, Drive, Archive, API
from relic.sga.v2._serializers import ArchiveSerializer


def generate_file(name: str, data: bytes, storage: StorageType, compressed: bool = False, parent: Optional[Union[Drive, Folder]] = None) -> File:
    return File(name, data, storage, compressed, None, parent, None)


def generate_folder(name: str, folders: Optional[List[Folder]] = None, files: Optional[List[File]] = None, parent: Optional[Union[Drive, Folder]] = None) -> Folder:
    folders = [] if folders is None else folders
    files = [] if files is None else files
    return Folder(name, folders, files, parent=parent)


def generate_drive(name: str, folders: Optional[List[Folder]] = None, files: Optional[List[File]] = None, alias: str = "data") -> Drive:
    folders = [] if folders is None else folders
    files = [] if files is None else files
    return Drive(alias, name, folders, files)


def generate_archive_meta(stream: BinaryIO, header_pos: int, header_size: int) -> ArchiveMetadata:
    header_helper = Md5ChecksumHelper(None, None, header_pos, header_size, ArchiveSerializer.HEADER_MD5_EIGEN)
    file_helper = Md5ChecksumHelper(None, None, header_pos, None, ArchiveSerializer.FILE_MD5_EIGEN)
    # Setup expected MD5 results
    header_helper.expected = header_helper.read(stream)
    file_helper.expected = file_helper.read(stream)
    return ArchiveMetadata(file_helper, header_helper)


def generate_archive(name: str, meta: ArchiveMetadata = None, drives: Optional[List[Drive]] = None) -> Archive:
    drives = [] if drives is None else drives
    return Archive(name, meta, drives)
