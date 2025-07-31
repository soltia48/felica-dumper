"""Text output manager for FeliCa Dumper results."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import ServiceResult
from .formatters import KeyVersionFormatter


class TextOutputManager:
    """Manages text file output for FeliCa Dumper results."""

    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.formatter = KeyVersionFormatter()
        self.content_lines: list[str] = []

    def _strip_rich_markup(self, text: str) -> str:
        """Remove Rich markup from text."""
        # Remove Rich color/style tags like [bold], [red], [/red], etc.
        clean_text = re.sub(r"\[/?[^\]]*\]", "", text)
        # Remove emoji and special characters that might not display well in plain text
        # Keep basic emojis but remove complex formatting
        return clean_text.strip()

    def _add_header(self, keys_file: str) -> None:
        """Add file header with timestamp and configuration."""
        self.content_lines.extend(
            [
                "FeliCa Dumper Results",
                "=" * 50,
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Keys file: {keys_file}",
                "",
            ]
        )

    def _add_system_overview(
        self,
        system_code: int,
        idm: bytes,
        pmm: bytes,
        keys_count: int,
        areas_count: int,
        services_count: int,
    ) -> None:
        """Add system overview section."""
        overview_lines = [
            f"System 0x{system_code:04X} Overview",
            "=" * 30,
        ]

        overview_lines.extend(
            [
                f"IDm: {idm.hex().upper()}",
                f"PMm: {pmm.hex().upper()}",
                f"Available Keys: {keys_count}",
                f"Discovered Areas: {areas_count}",
                f"Found Services: {services_count}",
                "",
            ]
        )

        self.content_lines.extend(overview_lines)

    def _add_areas_section(
        self, areas: list[tuple[int, int]], key_versions: dict[str, Any]
    ) -> None:
        """Add areas information section."""
        if not areas:
            return

        self.content_lines.extend(
            [
                "Areas",
                "=" * 20,
            ]
        )

        for i, (start, end) in enumerate(areas):
            key_info = "Not available"
            if (start, end) in key_versions["areas"]:
                result = key_versions["areas"][(start, end)]
                key_info = self._strip_rich_markup(
                    self.formatter.format_key_version(result)
                )

            area_range = self.formatter.format_area_range(start, end)
            self.content_lines.append(f"Area {i+1}: {area_range} - {key_info}")

        self.content_lines.append("")

    def _add_service_results(self, results: list[ServiceResult]) -> None:
        """Add service results section."""
        if not results:
            self.content_lines.extend(
                ["Service Results", "=" * 30, "No service results to display", ""]
            )
            return

        self.content_lines.extend(
            [
                "Service Results",
                "=" * 30,
            ]
        )

        for idx, result in enumerate(results, 1):
            service_display = self.formatter.format_service_codes(result.service_codes)

            # Status and basic info
            status = "Success" if result.success else "Failed"
            perf_indicator = ""
            if result.success:
                if result.processing_time < 1.0:
                    perf_indicator = " (Fast)"
                elif result.processing_time < 3.0:
                    perf_indicator = " (Normal)"
                else:
                    perf_indicator = " (Slow)"

            self.content_lines.extend(
                [
                    f"Service {service_display} | {status} | {result.block_count} blocks | {result.processing_time:.2f}s{perf_indicator}",
                    "-" * 60,
                ]
            )

            # Authentication information
            auth_status = result.used_keys.authentication_status
            if auth_status == "none":
                self.content_lines.append("Authentication: No authentication required")
            elif auth_status == "successful":
                self.content_lines.append("Authentication: Successful")

                # System key
                if result.used_keys.system_key:
                    sys_key = result.used_keys.system_key
                    key_info = self._strip_rich_markup(
                        self.formatter.format_key_info(sys_key)
                    )
                    self.content_lines.append(f"  System Key: {key_info}")

                # Area keys
                if result.used_keys.area_keys:
                    area_keys_display = []
                    for key in result.used_keys.area_keys:
                        key_info = self._strip_rich_markup(
                            self.formatter.format_key_info(key)
                        )
                        area_keys_display.append(key_info)
                    self.content_lines.append(
                        f"  Area Keys: {', '.join(area_keys_display)}"
                    )

                # Service keys
                if result.used_keys.service_keys:
                    service_keys_display = []
                    for key in result.used_keys.service_keys:
                        key_info = self._strip_rich_markup(
                            self.formatter.format_key_info(key)
                        )
                        service_keys_display.append(key_info)
                    self.content_lines.append(
                        f"  Service Keys: {', '.join(service_keys_display)}"
                    )

            elif auth_status == "failed_missing_keys":
                self.content_lines.append(
                    "Authentication: Failed - Missing required keys"
                )
            elif auth_status == "failed_error":
                self.content_lines.append(
                    "Authentication: Failed - Authentication error"
                )

            # Block data
            if result.success and result.output_lines:
                block_lines = [line for line in result.output_lines if "Block" in line]
                if block_lines:
                    self.content_lines.append("Block Data:")
                    for line in block_lines:
                        clean_line = self._strip_rich_markup(line)
                        self.content_lines.append(f"  {clean_line}")

                # Additional output
                other_lines = [
                    line
                    for line in result.output_lines
                    if "Block" not in line and line.strip()
                ]
                if other_lines:
                    self.content_lines.append("Additional Info:")
                    for line in other_lines[:5]:  # Limit to first 5 lines
                        clean_line = self._strip_rich_markup(line)
                        self.content_lines.append(f"  {clean_line}")
                    if len(other_lines) > 5:
                        self.content_lines.append(
                            f"  ... {len(other_lines) - 5} more lines"
                        )

            elif not result.success and result.output_lines:
                self.content_lines.append("Error Details:")
                for line in result.output_lines[:3]:  # Show first 3 error lines
                    clean_line = self._strip_rich_markup(line)
                    self.content_lines.append(f"  {clean_line}")
                if len(result.output_lines) > 3:
                    self.content_lines.append(
                        f"  ... {len(result.output_lines) - 3} more error lines"
                    )

            self.content_lines.append("")

    def _add_summary(
        self,
        successful: int,
        failed: int,
        total_blocks: int,
        total_time: float,
        processing_time: float,
    ) -> None:
        """Add final summary section."""
        total_services = successful + failed
        success_rate = (successful / total_services * 100) if total_services > 0 else 0

        status_text = (
            "Excellent"
            if success_rate >= 90
            else (
                "Good"
                if success_rate >= 75
                else "Partial" if success_rate >= 50 else "Poor"
            )
        )

        avg_time = (total_time / total_services) if total_services > 0 else 0

        self.content_lines.extend(
            [
                "Final Summary",
                "=" * 30,
                f"Processing Complete - {status_text} Results",
                "",
                f"Successful Services: {successful}",
                f"Failed Services: {failed}",
                f"Success Rate: {success_rate:.1f}%",
                f"Total Blocks Read: {total_blocks:,}",
                f"Service Processing Time: {total_time:.2f}s",
                f"Total Session Time: {processing_time:.2f}s",
                f"Average per Service: {avg_time:.2f}s",
                "",
            ]
        )

    def write_system_data(
        self,
        system_code: int,
        idm: bytes,
        pmm: bytes,
        keys_file: str,
        keys_count: int,
        areas_count: int,
        services_count: int,
        areas: list[tuple[int, int]],
        key_versions: dict[str, Any],
        results: list[ServiceResult],
        successful: int,
        failed: int,
        total_blocks: int,
        total_time: float,
        processing_time: float,
    ) -> None:
        """Write complete system data to text file."""
        # Clear previous content for new system
        if not self.content_lines:  # Only add header for first system
            self._add_header(keys_file)

        self._add_system_overview(
            system_code,
            idm,
            pmm,
            keys_count,
            areas_count,
            services_count,
        )
        self._add_areas_section(areas, key_versions)
        self._add_service_results(results)
        self._add_summary(successful, failed, total_blocks, total_time, processing_time)

        # Add separator for multiple systems
        self.content_lines.extend(["=" * 80, ""])

    def save_to_file(self) -> None:
        """Save all collected content to the output file."""
        try:
            # Create directory if it doesn't exist
            self.output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self.content_lines))

        except Exception as e:
            raise IOError(
                f"Failed to write to output file {self.output_file}: {str(e)}"
            )

    def get_output_path(self) -> str:
        """Get the absolute path of the output file."""
        return str(self.output_file.absolute())
