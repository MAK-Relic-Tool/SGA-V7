"""
Error definitions for the SGA API
"""
from typing import List, Optional

from relic.core.errors import MismatchError
from relic.sga._core import Version


class VersionMismatchError(MismatchError[Version]):
    """
    A version did not match the version expected.
    """

    def __init__(
        self, received: Optional[Version] = None, expected: Optional[Version] = None
    ):
        super().__init__("Version", received, expected)


class MD5MismatchError(MismatchError[bytes]):
    """
    An archive or file did not pass the redundancy check.
    """

    def __init__(
        self, received: Optional[bytes] = None, expected: Optional[bytes] = None
    ):
        super().__init__("MD5", received, expected)


class VersionNotSupportedError(Exception):
    """
    An unknown version was provided.
    """

    def __init__(self, received: Version, allowed: List[Version]):
        super().__init__()
        self.received = received
        self.allowed = allowed

    def __str__(self) -> str:
        def str_ver(version: Version) -> str:  # dont use str(version); too verbose
            return f"{version.major}.{version.minor}"

        allowed_str = [str_ver(_) for _ in self.allowed]
        return f"Version `{str_ver(self.received)}` is not supported. Versions supported: `{allowed_str}`"


class DecompressedSizeMismatch(MismatchError[int]):
    """
    A file was decompressed, but did not pass the redundancy check.
    """

    def __init__(self, received: Optional[int] = None, expected: Optional[int] = None):
        super().__init__("Decompressed Size", received, expected)


__all__ = [
    "VersionMismatchError",
    "MD5MismatchError",
    "VersionNotSupportedError",
    "DecompressedSizeMismatch",
]
