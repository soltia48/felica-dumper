"""FeliCa tag reading functionality."""

import itertools

from rich.console import Console

from nfc.tag.tt3_sony import FelicaStandard
from nfc.tag.tt3 import ServiceCode, BlockCode, Type3TagCommandError

from ..models import MAX_BATCH_SIZE

console = Console()


class TagReader:
    """Handles FeliCa tag reading operations."""

    def __init__(self, tag: FelicaStandard):
        self.tag = tag

    def discover_areas_and_services(self) -> tuple[list[tuple[int, int]], list[int]]:
        """Discover areas and services on the tag.

        Returns:
            Tuple of (areas, services) where areas is list of (start, end) tuples
            and services is list of service codes
        """
        areas = []
        services = []

        for service_index in itertools.count():
            if service_index >= 0x10000:
                break

            area_or_service = self.tag.search_service_code(service_index)
            if area_or_service is None:
                break

            if len(area_or_service) == 1:
                services.append(area_or_service[0])
            elif len(area_or_service) == 2:
                areas.append((area_or_service[0], area_or_service[1]))

        return areas, services

    def get_key_versions(
        self,
        system_code: int,
        areas: list[tuple[int, int]],
        services: list[int],
    ) -> dict:
        """Get key versions for system, areas, and services using both v1 and v2 methods.

        Args:
            system_code: The current system code
            areas: List of (area_start, area_end) tuples
            services: List of service codes

        Returns:
            Dictionary with 'system', 'areas', and 'services' key version results
        """
        results = {"system": {}, "areas": {}, "services": {}}

        # System key version (always use 0xFFFF)
        system_service_code = ServiceCode(0xFFFF >> 6, 0xFFFF & 0x3F)
        try:
            system_results = self._get_key_versions_batch([system_service_code])
            if system_results is not None:
                results["system"][system_code] = system_results[0]
        except Exception as e:
            console.print(
                f"[yellow]⚠️  Warning: Failed to get system key version: {e}[/yellow]"
            )

        # Area key versions (using area_start)
        if areas:
            area_converter = lambda area: ServiceCode(area[0] >> 6, area[0] & 0x3F)
            area_results = self._process_codes_in_batches(areas, area_converter, "area")
            results["areas"] = area_results

        # Service key versions
        if services:
            service_converter = lambda service: ServiceCode(
                service >> 6, service & 0x3F
            )
            service_results = self._process_codes_in_batches(
                services, service_converter, "service"
            )
            results["services"] = service_results

        return results

    def _get_key_versions_batch(
        self, service_codes: list[ServiceCode]
    ) -> list[int] | list[tuple[int, int | None]] | None:
        """Get key versions for a batch of service codes, trying v2 first then v1.

        Args:
            service_codes: List of ServiceCode objects (max 32)

        Returns:
            First successful result: v2_results (list of tuples) or v1_results (list of ints) or None if both fail
        """
        # Try v2 first
        try:
            return self.tag.request_service_v2(service_codes)
        except Exception:
            pass

        # Fall back to v1 if v2 fails
        try:
            return self.tag.request_service(service_codes)
        except Exception:
            return None

    def _process_codes_in_batches(
        self, codes: list, code_converter, code_type: str
    ) -> dict:
        """Process codes in batches of 32 and return key version results.

        Args:
            codes: List of codes to process
            code_converter: Function to convert code to ServiceCode
            code_type: Type name for error messages

        Returns:
            Dictionary mapping codes to key version results (v1 int or v2 tuple)
        """
        results = {}

        for i in range(0, len(codes), MAX_BATCH_SIZE):
            batch_codes = codes[i : i + MAX_BATCH_SIZE]
            service_codes = [code_converter(code) for code in batch_codes]

            try:
                batch_results = self._get_key_versions_batch(service_codes)
                if batch_results is not None:
                    for j, code in enumerate(batch_codes):
                        results[code] = batch_results[j]
            except Exception as e:
                batch_num = i // MAX_BATCH_SIZE + 1
                console.print(
                    f"[yellow]⚠️  Warning: Failed to get {code_type} key versions (batch {batch_num}): {e}[/yellow]"
                )

        return results

    def read_blocks_without_encryption(
        self, service_code: int, max_blocks: int = 0x10000
    ) -> tuple[list[str], int]:
        """Read blocks from a service without encryption.

        Args:
            service_code: Service code to read from
            max_blocks: Maximum number of blocks to attempt

        Returns:
            Tuple of (output_lines, block_count)
        """
        output_lines = []

        try:
            # Create ServiceCode object
            service_number = service_code >> 6
            service_attribute = service_code & 0x3F
            sc = ServiceCode(service_number, service_attribute)

            block_count = 0
            for block_number in range(max_blocks):
                try:
                    service_list = [sc]
                    block_list = [BlockCode(block_number)]
                    block_data = self.tag.read_without_encryption(
                        service_list, block_list
                    )

                    if block_data and len(block_data) >= 16:
                        block_bytes = block_data[:16]
                        output_lines.append(
                            f"    Block {block_number:04X}: {block_bytes.hex()}"
                        )
                        block_count += 1
                    else:
                        break

                except Type3TagCommandError:
                    break

            return output_lines, block_count

        except Exception as e:
            output_lines.append(f"  ✗ Failed to read without authentication: {e}")
            return output_lines, 0

    def read_blocks_with_authentication(
        self, service_index: int, max_blocks: int = 0x10000
    ) -> tuple[list[str], int]:
        """Read blocks using authenticated read_blocks method.

        Args:
            service_index: Service index (from authentication)
            max_blocks: Maximum number of blocks to attempt

        Returns:
            Tuple of (output_lines, block_count)
        """
        output_lines = []

        try:
            block_count = 0
            for block_number in range(max_blocks):
                try:
                    elements = [(service_index, block_number)]
                    block_data = self.tag.read_blocks(elements)

                    if block_data and len(block_data) > 0:
                        output_lines.append(
                            f"    Block {block_number:04X}: {block_data[0].hex()}"
                        )
                        block_count += 1
                    else:
                        break

                except Type3TagCommandError:
                    break

            return output_lines, block_count

        except Exception as e:
            output_lines.append(f"  ✗ Failed to read blocks: {e}")
            return output_lines, 0

    def reset_authentication(self):
        """Reset tag authentication state."""
        self.tag.reset_authentication()
