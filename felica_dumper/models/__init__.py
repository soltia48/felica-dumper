"""Data models for FeliCa Dumper."""

from .key_info import KeyInfo, UsedKeys
from .service_result import ServiceResult
from .constants import *

__all__ = [
    "KeyInfo",
    "UsedKeys",
    "ServiceResult",
    "MAX_BATCH_SIZE",
    "SYSTEM_KEY_NODE_ID",
    "ROOT_AREA_KEY_NODE_ID",
    "AREA_KEY_THRESHOLD",
    "MAX_BLOCKS",
]
