"""Display management for FeliCa Dumper UI."""

from rich.console import Console
from rich.tree import Tree

from ..models import ServiceResult
from .formatters import KeyVersionFormatter


class DisplayManager:
    """Manages all UI display operations."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.formatter = KeyVersionFormatter()

    BLOCK_PREVIEW_LIMIT = 16

    def create_service_tree(
        self,
        system_code: int,
        areas: list[tuple[int, int]],
        service_groups: list[list[int]],
        key_versions: dict,
        service_results: list[ServiceResult] | None = None,
        identifiers: dict[str, str | None] | None = None,
    ) -> Tree:
        """Create a tree structure displaying system, areas, and services."""
        system_label = f"[bold blue]System 0x{system_code:04X}[/bold blue]"
        system_key = key_versions.get("system", {}).get(system_code)
        if system_key is not None:
            system_label += (
                f"  [dim]Key[/dim] {self.formatter.format_key_version(system_key)}"
            )

        tree = Tree(system_label)
        tree.add(
            f"[dim]Areas discovered: {len(areas)} | Service groups: {len(service_groups)}[/dim]"
        )

        if identifiers:
            idm = identifiers.get("idm")
            pmm = identifiers.get("pmm")
            idi = identifiers.get("idi")
            pmi = identifiers.get("pmi")
            id_segments = []
            if idm:
                id_segments.append(f"IDm: {idm}")
            if pmm:
                id_segments.append(f"PMm: {pmm}")
            if idi:
                id_segments.append(f"IDi: {idi}")
            if pmi:
                id_segments.append(f"PMi: {pmi}")
            if id_segments:
                tree.add(f"[dim]{' | '.join(id_segments)}[/dim]")

        if service_results:
            success_count = sum(1 for r in service_results if r.success)
            failure_count = len(service_results) - success_count
            total_blocks = sum(r.block_count for r in service_results)
            tree.add(
                f"[dim]Processed services: {len(service_results)} | Success: {success_count} | "
                f"Failed: {failure_count} | Blocks: {total_blocks}[/dim]"
            )

        area_nodes, root_areas = self._build_area_hierarchy(areas)
        unassigned_groups = self._assign_service_groups_to_areas(
            area_nodes, service_groups
        )
        result_lookup = self._build_result_lookup(service_results)

        if root_areas:
            areas_node = tree.add("[cyan]Areas[/cyan]")
            for area in root_areas:
                self._add_area_branch(
                    areas_node, area, area_nodes, key_versions, result_lookup
                )
        else:
            tree.add("[dim]No areas discovered for this system[/dim]")

        # Unassigned services (service codes without matching area range)
        if unassigned_groups:
            services_node = tree.add("[yellow]Services without matching area[/yellow]")
            for group in unassigned_groups:
                self._add_service_group_node(
                    services_node, group, key_versions, result_lookup
                )

        return tree

    def _format_service_group_label(
        self,
        service_group: list[int],
        key_versions: dict,
        result: ServiceResult | None = None,
    ) -> str:
        """Format a service group label with authentication, key, and status information."""
        service_display = self.formatter.format_service_codes(service_group)
        if len(service_group) == 1:
            label = f"Service {service_display}"
        else:
            label = f"Service group {service_display}"

        auth_values = [bool(sc & 1) for sc in service_group]
        if all(auth_values):
            auth_text = "[green]no authentication required[/green]"
        elif any(auth_values):
            auth_text = "[yellow]mixed authentication requirements[/yellow]"
        else:
            auth_text = "[red]authentication required[/red]"

        label += f" ({auth_text})"

        key_info_parts = []
        for sc in service_group:
            key_result = key_versions.get("services", {}).get(sc)
            if key_result is not None:
                key_info_parts.append(
                    f"0x{sc:04X}:{self.formatter.format_key_version(key_result)}"
                )

        meta_segments: list[str] = []

        if result is not None:
            status_text = (
                "[green]success[/green]" if result.success else "[red]failed[/red]"
            )
            meta_segments.append(f"[dim]status[/dim] {status_text}")
            meta_segments.append(f"[cyan]{result.block_count} block(s)[/cyan]")

        if key_info_parts:
            meta_segments.append(f"[dim]keys[/dim] {', '.join(key_info_parts)}")

        if meta_segments:
            label += "  " + " | ".join(meta_segments)

        return label

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

    def _add_area_branch(
        self,
        parent_node: Tree,
        area: tuple[int, int],
        area_nodes: dict[tuple[int, int], dict],
        key_versions: dict,
        result_lookup: dict[tuple[int, ...], ServiceResult],
    ) -> None:
        """Recursively add an area and its descendants to the tree."""
        area_label = self._format_area_label(area, key_versions)
        current_node = parent_node.add(area_label)

        for group in area_nodes[area]["groups"]:
            self._add_service_group_node(
                current_node, group, key_versions, result_lookup
            )

        children = area_nodes[area]["children"]
        if children:
            for child in children:
                self._add_area_branch(
                    current_node, child, area_nodes, key_versions, result_lookup
                )

        if not children and not area_nodes[area]["groups"]:
            current_node.add("[dim]No services assigned to this area[/dim]")

    def _format_area_label(self, area: tuple[int, int], key_versions: dict) -> str:
        """Format area label with range and key information."""
        range_text = self.formatter.format_area_range(*area)
        label = f"Area [{range_text}]"

        area_key = key_versions.get("areas", {}).get(area)
        if area_key is not None:
            label += f"  [dim]Key[/dim] {self.formatter.format_key_version(area_key)}"

        return label

    def _build_result_lookup(
        self, service_results: list[ServiceResult] | None
    ) -> dict[tuple[int, ...], ServiceResult]:
        """Create a lookup from service code tuples to ServiceResult instances."""
        if not service_results:
            return {}

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

    def _add_service_group_node(
        self,
        parent_node: Tree,
        service_group: list[int],
        key_versions: dict,
        result_lookup: dict[tuple[int, ...], ServiceResult],
    ) -> None:
        """Add a service group node to the tree, including block data if available."""
        result = self._find_service_result(service_group, result_lookup)
        label = self._format_service_group_label(service_group, key_versions, result)
        group_node = parent_node.add(label)

        if result is None:
            return

        if result.success:
            self._add_block_lines(group_node, result)
        else:
            self._add_error_lines(group_node, result)

    def _add_block_lines(self, service_node: Tree, result: ServiceResult) -> None:
        """Add block data lines as children of the service node."""
        block_lines = [
            line.strip()
            for line in result.output_lines
            if "Block" in line and line.strip()
        ]

        if not block_lines:
            if result.block_count > 0:
                service_node.add(
                    f"[cyan]Read {result.block_count} block(s) (no textual data available)[/cyan]"
                )
            else:
                service_node.add("[dim]No block data available[/dim]")
            return

        preview = block_lines[: self.BLOCK_PREVIEW_LIMIT]
        for line in preview:
            service_node.add(f"[bold white]{line}[/bold white]")

        remaining = len(block_lines) - len(preview)
        if remaining > 0:
            service_node.add(f"[dim]… {remaining} more block line(s) omitted[/dim]")

    def _add_error_lines(self, service_node: Tree, result: ServiceResult) -> None:
        """Add error lines for services that failed to process."""
        messages = [line.strip() for line in result.output_lines if line.strip()]

        if not messages:
            service_node.add("[red]Processing failed (no details available).[/red]")
            return

        preview = messages[:3]
        for line in preview:
            service_node.add(f"[red]{line}[/red]")

        remaining = len(messages) - len(preview)
        if remaining > 0:
            service_node.add(f"[dim]… {remaining} additional message(s)[/dim]")
