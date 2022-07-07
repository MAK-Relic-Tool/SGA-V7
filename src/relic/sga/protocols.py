"""
Defines protocols that the SGA API uses.
"""
from __future__ import annotations

from pathlib import PurePath
from typing import (
    TypeVar,
    Protocol,
    List,
    Optional,
    Iterable,
    BinaryIO,
    runtime_checkable,
    Sequence,
    Tuple,
)
from typing_extensions import TypeAlias

TParent = TypeVar("TParent")
TParent_co = TypeVar("TParent_co", covariant=True)
TArchive = TypeVar("TArchive")
TFolder = TypeVar("TFolder")
TFolder_co = TypeVar("TFolder_co", covariant=True)
TFile = TypeVar("TFile")
TFile_co = TypeVar("TFile_co", covariant=True)
T = TypeVar("T")


@runtime_checkable
class StreamSerializer(Protocol[T]):
    """Serializes the Type to/from a binary stream."""

    def unpack(self, stream: BinaryIO) -> T:
        """
        Converts binary data from the stream to parsed data.

        :param stream: The stream to read from.

        :return: The parsed data.
        """
        raise NotImplementedError

    def pack(self, stream: BinaryIO, value: T) -> int:
        """
        Converts binary data from the stream to parsed data.

        :param stream: The stream to write to.
        :param value: The data to convert to binary.

        :return: The number of bytes written.
        """
        raise NotImplementedError


@runtime_checkable
class IOPathable(Protocol):
    """
    Represents an object that has a path in an SGA file system.
    """

    # pylint: disable=too-few-public-methods
    @property
    def path(self) -> PurePath:
        """
        The path within the Archive.

        :return: The path within the Archive to this object.
        """
        raise NotImplementedError


class IOChild(Protocol[TParent]):
    """
    Represents an object that has a parent in an SGA file system.
    """

    # pylint: disable=too-few-public-methods
    parent: Optional[TParent]


class IOContainer(Protocol[TFolder, TFile]):
    """
    Represents an object that contains sub-files/sub-folders in an SGA file system.
    """

    # pylint: disable=too-few-public-methods
    sub_folders: List[TFolder]
    files: List[TFile]


IOWalkStep: TypeAlias = Tuple[TParent_co, Sequence[TFolder_co], Sequence[TFile_co]]
IOWalk: TypeAlias = Iterable[
    Tuple[TParent_co, Sequence[TFolder_co], Sequence[TFile_co]]
]


class IOWalkable(Protocol[TParent_co, TFolder_co, TFile_co]):
    """
    Represents an object that allows walking down its hierarchy in an SGA file system.
    """

    # pylint: disable=too-few-public-methods
    def walk(self) -> IOWalk[TParent_co, TFolder_co, TFile_co]:
        """
        Walk down the heirarchy of this object.

        :return: An iterable consisting of ('Current', 'Current Folders', 'Current Files').
        """
        raise NotImplementedError


class ArchiveIO(Protocol[TArchive]):
    """
    Represents a class which allows reading/writing an SGA Archive.
    """

    def read(
        self, stream: BinaryIO, lazy: bool = False, decompress: bool = True
    ) -> TArchive:
        """
        Converts an archive from its binary representation.

        :param stream: The stream to read from.
        :param lazy: Data within the SGA Archive will not be loaded until requested.
        :param decompress: Data within the SGA Archive will be decompressed.

        :return: The SGA Archive object read.

        :note:See :class:`~relic.sga._abc.File` for more information.
        """
        raise NotImplementedError

    def write(self, stream: BinaryIO, archive: TArchive) -> int:
        """
        Converts an archive to its binary representation.

        :param stream: The stream to write to.
        :param archive: The archive to write to the stream.

        :return: The number of bytes written.
        """
        raise NotImplementedError
