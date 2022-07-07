"""
Shared definitions used by several components of the module
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, BinaryIO

from serialization_tools.magic import MagicWordIO
from serialization_tools.structx import Struct

MagicWord = MagicWordIO(Struct("< 8s"), "_ARCHIVE".encode("ascii"))


@dataclass
class Version:
    """The Major Version; Relic refers to this as the 'Version'"""

    major: int
    """ The Minor Version; Relic refers to this as the 'Product' """
    minor: int = 0

    LAYOUT: ClassVar[Struct] = Struct("<2H")

    def __str__(self) -> str:
        return f"Version {self.major}.{self.minor}"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Version)
            and self.major == other.major
            and self.minor == other.minor
        )

    def __hash__(self) -> int:
        # if this was C we could guarantee the hash was unique
        # because major/minor would both be 16 bits and the hash would be 32
        # Since python doesn't allow that we just assume data isn't garbage;
        # garbage in => garbage out after all
        return self.major << 16 + self.minor

    @classmethod
    def unpack(cls, stream: BinaryIO) -> Version:
        """
        Reads a version from the stream.
        :param stream: Data stream to read from.
        :return: A new Version instance.
        """
        layout: Struct = cls.LAYOUT
        args = layout.unpack_stream(stream)
        return cls(*args)

    def pack(self, stream: BinaryIO) -> int:
        """
        Writes the version to the stream.
        :param stream: Data stream to write to.
        :return: Number of bytes written.
        """
        layout: Struct = self.LAYOUT
        args = (self.major, self.minor)
        packed: int = layout.pack_stream(stream, *args)
        return packed


class StorageType(int, Enum):
    """
    Specifies whether data is stored as a 'raw blob' or as a 'zlib compressed blob'
    """

    STORE = 0
    BUFFER_COMPRESS = 1
    STREAM_COMPRESS = 2


class VerificationType(int, Enum):
    """
    A 'Flag' used to specify how the data's Redundancy Check is stored.
    """

    NONE = 0  # unknown real values, assuming incremental
    CRC = 1  # unknown real values, assuming incremental
    CRC_BLOCKS = 2  # unknown real values, assuming incremental
    MD5_BLOCKS = 3  # unknown real values, assuming incremental
    SHA1_BLOCKS = 4  # unknown real values, assuming incremental
