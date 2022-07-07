"""
A library for reading & writing Relic's SGA archive files.
"""
from relic.sga._apis import apis as APIs, read
from relic.sga._core import Version, MagicWord, StorageType, VerificationType
__version__ = "2022.1rc0"
__all__ = [
    "read",
    "APIs",
    "Version",
    "MagicWord",
    "StorageType",
    "VerificationType",
]
