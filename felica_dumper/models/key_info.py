"""Key information data models."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class KeyInfo:
    """Data class to store key information"""

    node_id: int  # Node ID (hexadecimal value)
    version: int  # Key version
    key_value: bytes  # Actual key value (for internal processing, not displayed)
    key_type: str  # Key type ("system", "area", "service")

    def __str__(self) -> str:
        return (
            f"{self.key_type.capitalize()} Key 0x{self.node_id:04X} (v{self.version})"
        )


@dataclass
class UsedKeys:
    """Data class to store information about used keys"""

    system_key: KeyInfo | None = None  # System key
    area_keys: list[KeyInfo] = field(default_factory=list)  # List of area keys
    service_keys: list[KeyInfo] = field(default_factory=list)  # List of service keys
    authentication_required: bool = False  # Whether authentication was required
    authentication_status: Literal[
        "none", "successful", "failed_missing_keys", "failed_error"
    ] = "none"  # Authentication status
    issue_id: bytes | None = None  # IDi returned from authentication
    issue_parameter: bytes | None = None  # PMi returned from authentication

    def get_all_keys(self) -> list[KeyInfo]:
        """Get all used keys"""
        keys = []
        if self.system_key:
            keys.append(self.system_key)
        keys.extend(self.area_keys)
        keys.extend(self.service_keys)
        return keys
