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
        """Display service results with enhanced formatting and detailed block data."""
        if not results:
            self.console.print("[dim]No service results to display[/dim]")
            return

        # Header with results count
        results_header = Panel(
            f"[bold bright_blue]📋 Service Processing Results[/bold bright_blue]\n"
            f"[dim]Displaying {len(results)} service result(s)[/dim]",
            border_style="bright_blue",
            box=box.ROUNDED,
        )
        self.console.print(results_header)

        for idx, result in enumerate(results, 1):
            # Format service codes
            service_display = self.formatter.format_service_codes(result.service_codes)

            # Enhanced status with performance indicators
            if result.success:
                status_icon = "✅"
                status_text = "[bright_green]Success[/bright_green]"
                border_color = "bright_green"

                # Performance indicator based on processing time
                if result.processing_time < 1.0:
                    perf_icon = "⚡"
                    perf_text = "[green]Fast[/green]"
                elif result.processing_time < 3.0:
                    perf_icon = "🔄"
                    perf_text = "[yellow]Normal[/yellow]"
                else:
                    perf_icon = "🐌"
                    perf_text = "[orange3]Slow[/orange3]"
            else:
                status_icon = "❌"
                status_text = "[bright_red]Failed[/bright_red]"
                border_color = "bright_red"
                perf_icon = "⏸️"
                perf_text = "[dim]N/A[/dim]"

            # Create enhanced service header
            service_header = (
                f"[bold cyan]Service {service_display}[/bold cyan] | "
                f"{status_icon} {status_text} | "
                f"[magenta]📦 {result.block_count} blocks[/magenta] | "
                f"[yellow]⏱️  {result.processing_time:.2f}s[/yellow] | "
                f"{perf_icon} {perf_text}"
            )

            panel_content = service_header

            # Enhanced authentication information based on authentication status
            auth_status = result.used_keys.authentication_status

            if auth_status == "none":
                panel_content += f"\n\n[bold]🔓 Authentication:[/bold] [bright_green]No authentication required[/bright_green]"
            elif auth_status == "successful":
                auth_sections = []

                # System key section with enhanced formatting
                if result.used_keys.system_key:
                    sys_key = result.used_keys.system_key
                    auth_sections.append(
                        f"[bold bright_blue]🔐 System Key:[/bold bright_blue] {self.formatter.format_key_info(sys_key)}"
                    )

                # Area keys section
                if result.used_keys.area_keys:
                    area_keys_display = []
                    for key in result.used_keys.area_keys:
                        area_keys_display.append(self.formatter.format_key_info(key))
                    auth_sections.append(
                        f"[bold bright_green]🏛️  Area Keys:[/bold bright_green] {', '.join(area_keys_display)}"
                    )

                # Service keys section
                if result.used_keys.service_keys:
                    service_keys_display = []
                    for key in result.used_keys.service_keys:
                        service_keys_display.append(self.formatter.format_key_info(key))
                    auth_sections.append(
                        f"[bold magenta]⚙️  Service Keys:[/bold magenta] {', '.join(service_keys_display)}"
                    )

                if auth_sections:
                    auth_display = "\n".join(
                        [f"  {section}" for section in auth_sections]
                    )
                    panel_content += f"\n\n[bold]🔑 Authentication:[/bold] [bright_green]✅ Successful[/bright_green]\n{auth_display}"
            elif auth_status == "failed_missing_keys":
                panel_content += f"\n\n[bold]🔑 Authentication:[/bold] [bright_red]❌ Failed - Missing required keys[/bright_red]"
            elif auth_status == "failed_error":
                panel_content += f"\n\n[bold]🔑 Authentication:[/bold] [bright_red]❌ Failed - Authentication error[/bright_red]"

            # Enhanced block data display
            if result.success and result.output_lines:
                # Filter and format block data
                block_lines = [line for line in result.output_lines if "Block" in line]
                if block_lines:
                    block_display = "\n".join(block_lines)

                    panel_content += f"\n\n[bold]📊 Block Data:[/bold]\n[bright_green]{block_display}[/bright_green]"

                # Show additional output if available
                other_lines = [
                    line
                    for line in result.output_lines
                    if "Block" not in line and line.strip()
                ]
                if other_lines:
                    other_display = "\n".join(
                        other_lines[:2]
                    )  # Show first 2 non-block lines
                    if len(other_lines) > 2:
                        other_display += (
                            f"\n[dim]... {len(other_lines) - 2} more lines[/dim]"
                        )
                    panel_content += f"\n\n[bold]📝 Additional Info:[/bold]\n[cyan]{other_display}[/cyan]"

            elif not result.success and result.output_lines:
                # Enhanced error information
                error_lines = result.output_lines[:3]  # Show first 3 error lines
                error_display = "\n".join(error_lines)
                if len(result.output_lines) > 3:
                    error_display += f"\n[dim]... {len(result.output_lines) - 3} more error lines[/dim]"
                panel_content += f"\n\n[bold]💥 Error Details:[/bold]\n[bright_red]{error_display}[/bright_red]"

            # Display the enhanced panel
            panel_title = (
                f"[bold]{idx}/{len(results)}: Service {service_display}[/bold]"
            )
            service_panel = Panel(
                panel_content,
                title=panel_title,
                border_style=border_color,
                box=box.ROUNDED,
                expand=False,
            )
            self.console.print(service_panel)

            # Add subtle spacing between services
            if idx < len(results):
                self.console.print()

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
