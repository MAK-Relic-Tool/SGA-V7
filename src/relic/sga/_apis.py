from typing import Dict, BinaryIO, Any, Optional

from typing_extensions import TypeAlias

from relic.sga import v2, v5, v7, v9, _abc
from relic.sga._core import Version, MagicWord
from relic.sga.protocols import ArchiveIO

AnyArchive: TypeAlias = _abc.Archive[Any, Any]
AnyArchiveIO: TypeAlias = ArchiveIO[AnyArchive]

apis: Dict[Version, AnyArchiveIO] = {
    v2.version: v2.ArchiveIO,
    v5.version: v5.ArchiveIO,
    v7.version: v7.ArchiveIO,
    v9.version: v9.ArchiveIO,
}


def read(
    stream: BinaryIO,
    lazy: bool = False,
    decompress: bool = True,
    api_lookup: Optional[Dict[Version, AnyArchiveIO]] = None,
) -> AnyArchive:
    api_lookup = api_lookup if api_lookup is not None else apis
    MagicWord.read_magic_word(stream)
    version = Version.unpack(stream)
    api = api_lookup[version]
    return api.read(stream, lazy, decompress)
