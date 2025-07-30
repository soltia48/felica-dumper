"""Service result data model."""

from dataclasses import dataclass, field
from .key_info import UsedKeys


@dataclass
class ServiceResult:
    """Store the result of processing a service or service group."""

    service_codes: list[int]  # List of service codes in the group
    output_lines: list[str]  # All output lines for this service/group
    success: bool  # Whether processing was successful
    block_count: int = 0  # Number of blocks read
    processing_time: float = 0.0  # Time taken to process
    used_keys: UsedKeys = field(default_factory=UsedKeys)  # Information about used keys

    @property
    def primary_service_code(self) -> int:
        """Return the primary service code for sorting purposes."""
        return min(self.service_codes)
