"""Display management for FeliCa Dumper UI."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.align import Align
from rich import box

from ..models import ServiceResult
from .formatters import KeyVersionFormatter


class DisplayManager:
    """Manages all UI display operations."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.formatter = KeyVersionFormatter()

    def show_header(self, tag_product: str):
        """Display the main header."""
        self.console.print(
            Panel(
                Align.center("[bold blue]FeliCa Card Reader[/bold blue]"),
                box=box.DOUBLE,
                border_style="blue",
            )
        )
        self.console.print(
            Panel(
                f"[bold blue]📱 FeliCa Card Reader[/bold blue]\n[dim]Connected: {tag_product}[/dim]",
                box=box.DOUBLE,
                border_style="blue",
            )
        )

    def show_system_header(self, system_code: int):
        """Display system header."""
        self.console.print(
            f"\n[bold magenta]🏢 System 0x{system_code:04X}[/bold magenta]"
        )

    def show_system_info(self, keys_count: int, areas_count: int, services_count: int):
        """Display system information panel."""
        info_text = f"[green]🔑 Keys Loaded:[/green] {keys_count}\n"
        info_text += f"[blue]🏛️  Areas Found:[/blue] {areas_count}\n"
        info_text += f"[cyan]⚙️  Services Found:[/cyan] {services_count}"

        self.console.print(
            Panel(info_text, title="System Information", box=box.ROUNDED)
        )

    def show_system_key_version(self, system_code: int, key_versions: dict):
        """Display system key version."""
        if system_code in key_versions["system"]:
            result = key_versions["system"][system_code]
            key_display = self.formatter.format_key_version(result)
            self.console.print(f"[bold]System Key Version:[/bold] {key_display}")

    def show_areas_table(self, areas: list[tuple[int, int]], key_versions: dict):
        """Display areas table."""
        if not areas:
            return

        area_table = Table(title="🏛️  Areas", box=box.SIMPLE)
        area_table.add_column("Area", style="cyan")
        area_table.add_column("Range", style="yellow")
        area_table.add_column("Key Version", style="green")

        for i, (start, end) in enumerate(areas):
            key_info = "Not available"
            if (start, end) in key_versions["areas"]:
                result = key_versions["areas"][(start, end)]
                key_info = self.formatter.format_key_version(result)

            area_table.add_row(
                f"Area {i+1}", self.formatter.format_area_range(start, end), key_info
            )

        self.console.print(area_table)

    def create_service_tree(self, service_groups: list, key_versions: dict) -> Tree:
        """Create a tree structure for displaying services."""
        tree = Tree("📊 [bold blue]Services & Areas[/bold blue]")

        group_num = 1
        for service_group in service_groups:
            if len(service_group) == 1:
                service = service_group[0]
                auth_icon = "🔒" if not (service & 1) else "🔓"
                auth_text = (
                    "[red]Auth required[/red]"
                    if not (service & 1)
                    else "[green]No auth needed[/green]"
                )

                # Add key version information
                key_info = ""
                if service in key_versions["services"]:
                    result = key_versions["services"][service]
                    key_display = self.formatter.format_key_version(result)
                    key_info = f" - {key_display}"

                service_node = tree.add(
                    f"{auth_icon} [cyan]Service 0x{service:04X}[/cyan] ({auth_text}){key_info}"
                )
            else:
                service_codes = self.formatter.format_service_codes(service_group)
                auth_icons = []
                for sc in service_group:
                    auth_icons.append("🔒" if not (sc & 1) else "🔓")

                # Add key version information for overlapped services
                key_info_parts = []
                for sc in service_group:
                    if sc in key_versions["services"]:
                        result = key_versions["services"][sc]
                        key_display = self.formatter.format_key_version(result)
                        key_info_parts.append(f"0x{sc:04X}: {key_display}")

                key_info = ""
                if key_info_parts:
                    key_info = f" - {', '.join(key_info_parts)}"

                group_node = tree.add(
                    f"🔗 [yellow]Service Group[/yellow]: {service_codes} (Overlapped: {' '.join(auth_icons)}){key_info}"
                )

            group_num += 1

        return tree

    def show_processing_order(self, no_auth_count: int, auth_count: int):
        """Display processing order information."""
        self.console.print(
            f"\n[dim]Processing order: {no_auth_count} non-auth groups first, then {auth_count} auth groups[/dim]"
        )

    def display_service_results(self, results: list[ServiceResult]):
        """Display service results with detailed block data."""
        self.console.print("\n[bold blue]📋 Service Processing Results[/bold blue]")

        for result in results:
            # Format service codes
            service_display = self.formatter.format_service_codes(result.service_codes)

            # Status with icon
            status = (
                "[green]✅ Success[/green]"
                if result.success
                else "[red]❌ Failed[/red]"
            )

            # Create service panel
            service_info = f"[cyan]Service: {service_display}[/cyan] | {status} | "
            service_info += f"[magenta]Blocks: {result.block_count}[/magenta] | "
            service_info += f"[yellow]Time: {result.processing_time:.2f}s[/yellow]"

            # Create panel for this service
            panel_content = service_info

            # Add used keys information with refined display
            if result.used_keys.authentication_required:
                key_sections = []

                # System key section
                if result.used_keys.system_key:
                    sys_key = result.used_keys.system_key
                    key_sections.append(
                        f"[bold blue]🔐 System:[/bold blue] {self.formatter.format_key_info(sys_key)}"
                    )

                # Area keys section
                if result.used_keys.area_keys:
                    area_keys_str = ", ".join(
                        [
                            self.formatter.format_key_info(key)
                            for key in result.used_keys.area_keys
                        ]
                    )
                    key_sections.append(
                        f"[bold green]🏛️  Area:[/bold green] {area_keys_str}"
                    )

                # Service keys section
                if result.used_keys.service_keys:
                    service_keys_str = ", ".join(
                        [
                            self.formatter.format_key_info(key)
                            for key in result.used_keys.service_keys
                        ]
                    )
                    key_sections.append(
                        f"[bold magenta]⚙️  Service:[/bold magenta] {service_keys_str}"
                    )

                if key_sections:
                    keys_display = "\n".join(
                        [f"  {section}" for section in key_sections]
                    )
                    panel_content += (
                        f"\n\n[dim]🔑 Authentication Keys:[/dim]\n{keys_display}"
                    )
            else:
                panel_content += f"\n\n[dim]🔓 Authentication:[/dim] [green]Not authenticated[/green]"

            # Add block data if available
            if result.success and result.output_lines:
                block_data = "\n".join(
                    [line for line in result.output_lines if "Block" in line]
                )
                if block_data:
                    panel_content += (
                        f"\n\n[dim]Block Data:[/dim]\n[green]{block_data}[/green]"
                    )
            elif not result.success and result.output_lines:
                # Show error information
                error_info = "\n".join(result.output_lines)
                panel_content += (
                    f"\n\n[dim]Error Details:[/dim]\n[red]{error_info}[/red]"
                )

            # Display the panel
            self.console.print(
                Panel(
                    panel_content,
                    title=f"Service {service_display}",
                    border_style="green" if result.success else "red",
                    box=box.ROUNDED,
                    expand=False,
                )
            )
            self.console.print()  # Add spacing between services

    def create_summary_panel(
        self,
        successful: int,
        failed: int,
        total_blocks: int,
        total_time: float,
        warnings: int,
    ) -> Panel:
        """Create a summary panel with statistics."""
        success_rate = (
            (successful / (successful + failed)) * 100
            if (successful + failed) > 0
            else 0
        )

        summary_text = f"""[green]✅ Successful:[/green] {successful}
[red]❌ Failed:[/red] {failed}
[blue]📊 Success Rate:[/blue] {success_rate:.1f}%
[magenta]💾 Total Blocks:[/magenta] {total_blocks}
[yellow]⏱️  Total Time:[/yellow] {total_time:.2f}s
[orange3]⚠️  Warnings:[/orange3] {warnings}"""

        return Panel(
            summary_text,
            title="📈 Final Summary",
            border_style=(
                "green"
                if success_rate > 75
                else "yellow" if success_rate > 50 else "red"
            ),
            box=box.ROUNDED,
        )

    def show_main_header(self):
        """Display the main application header."""
        self.console.print(
            Panel(
                Align.center("[bold blue]FeliCa Dumper[/bold blue]"),
                box=box.DOUBLE,
                border_style="blue",
            )
        )
