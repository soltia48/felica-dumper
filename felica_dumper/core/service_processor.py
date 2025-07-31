"""Service processing functionality."""

import time

from rich.console import Console

from nfc.tag.tt3_sony import FelicaStandard
from ..models import (
    ServiceResult,
    UsedKeys,
    KeyInfo,
    SERVICE_RANDOM_TYPE,
    SERVICE_CYCLIC_TYPE,
    SERVICE_PURSE_TYPE,
    RANDOM_CYCLIC_ACCESS_TYPES,
    PURSE_ACCESS_TYPES,
    MAX_BLOCKS,
)
from .tag_reader import TagReader
from .authentication import AuthenticationHandler

console = Console()


class ServiceProcessor:
    """Processes FeliCa services and service groups."""

    def __init__(self, tag: FelicaStandard):
        self.tag = tag
        self.tag_reader = TagReader(tag)
        self.auth_handler = AuthenticationHandler(tag)

    def group_overlapped_services(self, services: list[int]) -> list[list[int]]:
        """
        Group overlapped services together based on FeliCa overlap rules.

        Services are considered overlapped if they have the same service type
        and service number but different access attributes.

        Args:
            services: List of service codes

        Returns:
            List of service groups, where each group contains overlapped services
        """
        service_groups = []
        current_group = []

        for service in services:
            if not current_group:
                current_group = [service]
            else:
                # Check if this service overlaps with the current group
                last_service = current_group[-1]

                # Services overlap if they have the same service type and number
                # Service type is in bits 4-7, service number is in bits 6-15
                if service >> 4 == last_service >> 4:
                    if service >> 4 & 1:  # purse service
                        current_group.append(service)
                    elif service >> 2 == last_service >> 2:  # random/cyclic service
                        current_group.append(service)
                    else:
                        # Different service, start new group
                        service_groups.append(current_group)
                        current_group = [service]
                else:
                    # Different service, start new group
                    service_groups.append(current_group)
                    current_group = [service]

        if current_group:
            service_groups.append(current_group)

        return service_groups

    def process_service_group(
        self,
        service_group: list[int],
        areas: list[tuple[int, int]],
        keys: dict[int, KeyInfo],
    ) -> ServiceResult:
        """
        Process a group of overlapped services.

        Args:
            service_group: List of overlapped service codes
            areas: List of all discovered areas
            keys: Dictionary of keys

        Returns:
            ServiceResult object with processing results
        """
        start_time = time.time()
        output_lines = []
        used_keys = UsedKeys()

        if len(service_group) == 1:
            # Single service, use existing logic
            return self._process_single_service(service_group[0], areas, keys)

        # Multiple overlapped services
        service_codes = " & ".join([f"0x{sc:04X}" for sc in service_group])

        # Determine service type and access modes
        first_service = service_group[0]
        service_type = self._get_service_type(first_service)

        # Show access types for each service
        access_types = []
        for service in service_group:
            access_type = self._get_access_type(service, service_type)
            access_types.append(access_type)

        # Try to find a service that doesn't require authentication first
        no_auth_services = [sc for sc in service_group if sc & 1]

        success = False
        block_count = 0

        if no_auth_services:
            # Use the last service that doesn't require authentication
            selected_service = no_auth_services[-1]
            success, block_count, output_lines = self._read_without_authentication(
                selected_service, used_keys
            )
        else:
            # All services require authentication, try the first one
            selected_service = service_group[0]
            success, block_count, output_lines = self._read_with_authentication(
                selected_service, areas, keys, used_keys
            )

        processing_time = time.time() - start_time

        return ServiceResult(
            service_codes=service_group,
            output_lines=output_lines,
            success=success,
            block_count=block_count,
            processing_time=processing_time,
            used_keys=used_keys,
        )

    def _process_single_service(
        self,
        service_code: int,
        areas: list[tuple[int, int]],
        keys: dict[int, KeyInfo],
    ) -> ServiceResult:
        """Process a single service."""
        start_time = time.time()
        output_lines = []
        used_keys = UsedKeys()

        # Check if service requires authentication (LSB = 0) or not (LSB = 1)
        needs_auth = self.auth_handler.requires_authentication(service_code)

        success = False
        block_count = 0

        if needs_auth:
            success, block_count, output_lines = self._read_with_authentication(
                service_code, areas, keys, used_keys
            )
        else:
            success, block_count, output_lines = self._read_without_authentication(
                service_code, used_keys
            )

        processing_time = time.time() - start_time

        return ServiceResult(
            service_codes=[service_code],
            output_lines=output_lines,
            success=success,
            block_count=block_count,
            processing_time=processing_time,
            used_keys=used_keys,
        )

    def _read_without_authentication(
        self,
        service_code: int,
        used_keys: UsedKeys,
    ) -> tuple[bool, int, list[str]]:
        """Read service data without authentication."""
        try:
            # Record that no authentication was required
            used_keys.authentication_required = False
            used_keys.authentication_status = "none"

            output_lines, block_count = self.tag_reader.read_blocks_without_encryption(
                service_code, MAX_BLOCKS
            )

            return True, block_count, output_lines

        except Exception as e:
            error_lines = [f"  ✗ Failed to read without authentication: {e}"]
            return False, 0, error_lines

    def _read_with_authentication(
        self,
        service_code: int,
        areas: list[tuple[int, int]],
        keys: dict[int, KeyInfo],
        used_keys: UsedKeys,
    ) -> tuple[bool, int, list[str]]:
        """Read service data with authentication."""
        try:
            # Authenticate
            auth_success, error_messages = self.auth_handler.authenticate_service(
                service_code, areas, keys, used_keys
            )

            if not auth_success:
                # Check if failure was due to missing keys
                missing_key_errors = [
                    msg for msg in error_messages if "not found" in msg
                ]
                if missing_key_errors:
                    used_keys.authentication_status = "failed_missing_keys"
                else:
                    used_keys.authentication_status = "failed_error"
                return False, 0, error_messages

            # Authentication successful
            used_keys.authentication_status = "successful"

            # Read blocks using authenticated method
            output_lines, block_count = self.tag_reader.read_blocks_with_authentication(
                0, MAX_BLOCKS  # service_index = 0 since we authenticated one service
            )

            return True, block_count, output_lines

        except Exception as e:
            used_keys.authentication_status = "failed_error"
            error_lines = [f"  ✗ Authentication/read failed: {e}"]
            return False, 0, error_lines

    def _get_service_type(self, service_code: int) -> str:
        """Get service type string from service code."""
        service_type_bits = service_code >> 2 & 0b1111

        if service_type_bits == SERVICE_RANDOM_TYPE:
            return "Random"
        elif service_type_bits == SERVICE_CYCLIC_TYPE:
            return "Cyclic"
        elif service_type_bits & 0b1110 == SERVICE_PURSE_TYPE:
            return "Purse"
        else:
            return "Unknown"

    def _get_access_type(self, service_code: int, service_type: str) -> str:
        """Get access type string for a service code."""
        if service_type in ["Random", "Cyclic"]:
            return RANDOM_CYCLIC_ACCESS_TYPES[service_code & 3]
        elif service_type == "Purse":
            return PURSE_ACCESS_TYPES[service_code & 7]
        else:
            return "Unknown"
