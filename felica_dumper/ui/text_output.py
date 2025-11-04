"""Text output manager for FeliCa Dumper results."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import ServiceResult
from .formatters import KeyVersionFormatter


@dataclass
class SystemExportData:
    """Aggregated data for exporting a system report."""

    system_code: int
    idm: bytes
    pmm: bytes
    idi: bytes | str | None
    pmi: bytes | str | None
    keys_file: str
    keys_count: int
    areas_count: int
    services_count: int
    service_groups: list[list[int]]
    areas: list[tuple[int, int]]
    key_versions: dict[str, Any]
    results: list[ServiceResult]


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

    @staticmethod
    def _format_identifier(value: bytes | str | None) -> str:
        """Format identifier values to uppercase string representation."""
        if value is None:
            return "N/A"
        if isinstance(value, bytes):
            return value.hex().upper()
        if isinstance(value, str):
            return value.upper()
        try:
            return bytes(value).hex().upper()  # type: ignore[arg-type]
        except Exception:
            return str(value).upper()

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
        idi: bytes | str | None,
        pmi: bytes | str | None,
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
                f"IDi: {self._format_identifier(idi)}",
                f"PMi: {self._format_identifier(pmi)}",
                f"Available Keys: {keys_count}",
                f"Discovered Areas: {areas_count}",
                f"Found Services: {services_count}",
                "",
            ]
        )

        self.content_lines.extend(overview_lines)

    def _add_system_tree(
        self,
        areas: list[tuple[int, int]],
        service_groups: list[list[int]],
        key_versions: dict[str, Any],
        results: list[ServiceResult],
    ) -> None:
        """Add a hierarchy-style section similar to the CLI tree output."""
        self.content_lines.extend(
            [
                "Hierarchy",
                "=" * 20,
            ]
        )

        area_nodes, root_areas = self._build_area_hierarchy(areas)
        unassigned_groups = self._assign_service_groups_to_areas(
            area_nodes, service_groups
        )
        result_lookup = self._build_result_lookup(results)

        if root_areas:
            for area in root_areas:
                self._append_area_branch(
                    area=area,
                    nodes=area_nodes,
                    key_versions=key_versions,
                    result_lookup=result_lookup,
                    indent=0,
                )
        else:
            self.content_lines.append("No areas discovered for this system.")

        if unassigned_groups:
            if root_areas:
                self.content_lines.append("")
            self.content_lines.append("Services without matching area:")
            for group in unassigned_groups:
                self._append_service_group_line(
                    service_group=group,
                    key_versions=key_versions,
                    result_lookup=result_lookup,
                    indent=1,
                )

        self.content_lines.append("")

    def _append_area_branch(
        self,
        area: tuple[int, int],
        nodes: dict[tuple[int, int], dict],
        key_versions: dict[str, Any],
        result_lookup: dict[tuple[int, ...], ServiceResult],
        indent: int,
    ) -> None:
        """Append an area node and its children."""
        indent_str = "  " * indent
        label = self._format_area_label(area, key_versions)
        self.content_lines.append(f"{indent_str}{label}")

        groups = nodes[area]["groups"]
        if groups:
            for group in groups:
                self._append_service_group_line(
                    service_group=group,
                    key_versions=key_versions,
                    result_lookup=result_lookup,
                    indent=indent + 1,
                )
        else:
            self.content_lines.append(f"{indent_str}  (No services assigned)")

        for child in nodes[area]["children"]:
            self._append_area_branch(
                child, nodes, key_versions, result_lookup, indent + 1
            )

    def _append_service_group_line(
        self,
        service_group: list[int],
        key_versions: dict[str, Any],
        result_lookup: dict[tuple[int, ...], ServiceResult],
        indent: int,
    ) -> None:
        """Append a service group line with status and optional block data."""
        indent_str = "  " * indent
        label = self._compose_service_group_label(service_group, key_versions)

        result = self._find_service_result(service_group, result_lookup)
        meta_segments: list[str] = []
        if result is not None:
            status_text = "success" if result.success else "failed"
            meta_segments.append(f"status: {status_text}")
            meta_segments.append(f"blocks: {result.block_count}")

            if result.used_keys.authentication_status not in ("none", ""):
                meta_segments.append(
                    f"auth: {result.used_keys.authentication_status.replace('_', ' ')}"
                )

        key_info_parts = self._collect_service_key_info(service_group, key_versions)
        if key_info_parts:
            meta_segments.append(f"keys: {', '.join(key_info_parts)}")

        if meta_segments:
            label = f"{label} [{' | '.join(meta_segments)}]"

        self.content_lines.append(f"{indent_str}- {label}")

        if result is None:
            return

        if result.success:
            self._append_block_lines(result, indent + 2)
        else:
            self._append_error_lines(result, indent + 2)

    def _append_block_lines(self, result: ServiceResult, indent: int) -> None:
        """Append block data lines with indentation."""
        block_lines = [
            line.strip()
            for line in result.output_lines
            if "Block" in line and line.strip()
        ]
        indent_str = "  " * indent

        if not block_lines:
            if result.block_count > 0:
                self.content_lines.append(
                    f"{indent_str}(Read {result.block_count} block(s), no textual data)"
                )
            else:
                self.content_lines.append(f"{indent_str}(No block data available)")
            return

        for line in block_lines:
            clean_line = self._strip_rich_markup(line)
            self.content_lines.append(f"{indent_str}{clean_line}")

    def _append_error_lines(self, result: ServiceResult, indent: int) -> None:
        """Append error message lines with indentation."""
        messages = [line.strip() for line in result.output_lines if line.strip()]
        indent_str = "  " * indent

        if not messages:
            self.content_lines.append(
                f"{indent_str}(Processing failed with no additional details.)"
            )
            return

        preview = messages[:3]
        for line in preview:
            clean_line = self._strip_rich_markup(line)
            self.content_lines.append(f"{indent_str}{clean_line}")

        remaining = len(messages) - len(preview)
        if remaining > 0:
            self.content_lines.append(
                f"{indent_str}... {remaining} additional message(s)"
            )

    def _format_area_label(
        self, area: tuple[int, int], key_versions: dict[str, Any]
    ) -> str:
        """Format area label text with optional key version."""
        area_range = self.formatter.format_area_range(*area)
        key_info = ""
        if "areas" in key_versions and area in key_versions["areas"]:
            key_display = self.formatter.format_key_version(key_versions["areas"][area])
            key_info = f" - {self._strip_rich_markup(key_display)}"
        return f"Area [{area_range}]{key_info}"

    def _compose_service_group_label(
        self, service_group: list[int], key_versions: dict[str, Any]
    ) -> str:
        """Compose a textual description for a service group."""
        service_display = self.formatter.format_service_codes(service_group)
        if len(service_group) == 1:
            label = f"Service {service_display}"
        else:
            label = f"Service group {service_display}"

        auth_values = [bool(sc & 1) for sc in service_group]
        if all(auth_values):
            auth_text = "no authentication required"
        elif any(auth_values):
            auth_text = "mixed authentication requirements"
        else:
            auth_text = "authentication required"

        return f"{label} ({auth_text})"

    def _collect_service_key_info(
        self, service_group: list[int], key_versions: dict[str, Any]
    ) -> list[str]:
        """Collect key version information for service codes."""
        info: list[str] = []
        service_keys = key_versions.get("services", {})
        for sc in service_group:
            if sc in service_keys:
                key_display = self.formatter.format_key_version(service_keys[sc])
                info.append(f"0x{sc:04X}:{self._strip_rich_markup(key_display)}")
        return info

    def _build_area_hierarchy(
        self, areas: list[tuple[int, int]]
    ) -> tuple[dict[tuple[int, int], dict], list[tuple[int, int]]]:
        """Build parent-child relationships between areas based on containment."""
        if not areas:
            return {}, []

        nodes = {area: {"children": [], "groups": [], "parent": None} for area in areas}

        sorted_areas = sorted(areas, key=lambda a: (a[0], (a[1] - a[0]), a[1]))

        for current in sorted_areas:
            best_parent: tuple[int, int] | None = None
            smallest_size = None

            for candidate in sorted_areas:
                if candidate == current:
                    continue

                if candidate[0] <= current[0] and current[1] <= candidate[1]:
                    candidate_size = candidate[1] - candidate[0]
                    if smallest_size is None or candidate_size < smallest_size:
                        best_parent = candidate
                        smallest_size = candidate_size

            if best_parent is not None:
                nodes[current]["parent"] = best_parent
                nodes[best_parent]["children"].append(current)

        for node in nodes.values():
            node["children"].sort(key=lambda a: (a[0], (a[1] - a[0]), a[1]))

        root_areas = [area for area, data in nodes.items() if data["parent"] is None]
        root_areas.sort(key=lambda a: (a[0], (a[1] - a[0]), a[1]))

        return nodes, root_areas

    def _assign_service_groups_to_areas(
        self,
        area_nodes: dict[tuple[int, int], dict],
        service_groups: list[list[int]],
    ) -> list[list[int]]:
        """Assign service groups to the most specific area that contains them."""
        if not area_nodes:
            return service_groups.copy()

        unassigned: list[list[int]] = []

        for group in service_groups:
            if not group:
                continue

            primary = min(group)
            candidates = [area for area in area_nodes if area[0] <= primary <= area[1]]

            if not candidates:
                unassigned.append(group)
                continue

            target = min(candidates, key=lambda a: (a[1] - a[0], a[0], a[1]))
            area_nodes[target]["groups"].append(group)

        return unassigned

    def _build_result_lookup(
        self, service_results: list[ServiceResult]
    ) -> dict[tuple[int, ...], ServiceResult]:
        """Create a lookup from service code tuples to results."""
        lookup: dict[tuple[int, ...], ServiceResult] = {}
        for result in service_results:
            key = tuple(result.service_codes)
            lookup[key] = result
            sorted_key = tuple(sorted(result.service_codes))
            lookup[sorted_key] = result
        return lookup

    def _find_service_result(
        self,
        service_group: list[int],
        lookup: dict[tuple[int, ...], ServiceResult],
    ) -> ServiceResult | None:
        """Locate the ServiceResult corresponding to a service group."""
        if not lookup:
            return None

        key = tuple(service_group)
        if key in lookup:
            return lookup[key]

        sorted_key = tuple(sorted(service_group))
        return lookup.get(sorted_key)

    def write_system_data(self, data: SystemExportData) -> None:
        """Write complete system data to text file."""
        # Clear previous content for new system
        if not self.content_lines:  # Only add header for first system
            self._add_header(data.keys_file)

        self._add_system_overview(
            data.system_code,
            data.idm,
            data.pmm,
            data.idi,
            data.pmi,
            data.keys_count,
            data.areas_count,
            data.services_count,
        )
        self._add_system_tree(
            areas=data.areas,
            service_groups=data.service_groups,
            key_versions=data.key_versions,
            results=data.results,
        )

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
