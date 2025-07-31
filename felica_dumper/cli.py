"""Main CLI interface for FeliCa Dumper."""

import argparse
import time
from typing import Optional

import nfc
from nfc.tag import Tag
from nfc.tag.tt3_sony import FelicaStandard
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich import box

from .core import KeyManager, TagReader, ServiceProcessor
from .ui import DisplayManager
from .utils import optimize_service_processing_order

# Initialize Rich console with enhanced configuration
console = Console(force_terminal=True, width=120)


# Display constants for consistent styling
class DisplayStyle:
    """Constants for consistent display styling."""

    PRIMARY_COLOR = "bright_blue"
    SUCCESS_COLOR = "bright_green"
    ERROR_COLOR = "bright_red"
    WARNING_COLOR = "yellow"
    INFO_COLOR = "cyan"
    ACCENT_COLOR = "magenta"
    DIM_COLOR = "dim"

    HEADER_BOX = box.DOUBLE_EDGE
    PANEL_BOX = box.ROUNDED
    TABLE_BOX = box.SIMPLE_HEAD


class FelicaDumper:
    """Main FeliCa Dumper application with refined display."""

    def __init__(self, keys_file: str = "keys.csv"):
        self.console = console
        self.display = DisplayManager(console)
        self.keys_file = keys_file
        self.start_time = time.time()

    def _show_connection_status(self, tag: FelicaStandard) -> None:
        """Display enhanced connection status."""
        connection_panel = Panel(
            f"[{DisplayStyle.SUCCESS_COLOR}]✅ FeliCa Card Connected[/{DisplayStyle.SUCCESS_COLOR}]\n"
            f"[{DisplayStyle.INFO_COLOR}]📱 Product: {tag.product}[/{DisplayStyle.INFO_COLOR}]\n"
            f"[{DisplayStyle.DIM_COLOR}]🕐 Connected at: {time.strftime('%H:%M:%S')}[/{DisplayStyle.DIM_COLOR}]",
            title="[bold]Connection Status[/bold]",
            border_style=DisplayStyle.SUCCESS_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )
        self.console.print(connection_panel)

    def _create_system_overview_panel(
        self, system_code: int, keys_count: int, areas_count: int, services_count: int
    ) -> Panel:
        """Create an enhanced system overview panel."""
        overview_text = (
            f"[{DisplayStyle.ACCENT_COLOR}]🏢 System Code:[/{DisplayStyle.ACCENT_COLOR}] "
            f"[bold]0x{system_code:04X}[/bold]\n"
            f"[{DisplayStyle.SUCCESS_COLOR}]🔑 Available Keys:[/{DisplayStyle.SUCCESS_COLOR}] {keys_count}\n"
            f"[{DisplayStyle.INFO_COLOR}]🏛️  Discovered Areas:[/{DisplayStyle.INFO_COLOR}] {areas_count}\n"
            f"[{DisplayStyle.PRIMARY_COLOR}]⚙️  Found Services:[/{DisplayStyle.PRIMARY_COLOR}] {services_count}"
        )

        return Panel(
            overview_text,
            title=f"[bold {DisplayStyle.ACCENT_COLOR}]System 0x{system_code:04X} Overview[/bold {DisplayStyle.ACCENT_COLOR}]",
            border_style=DisplayStyle.ACCENT_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )

    def _show_processing_progress(
        self, description: str, total: Optional[int] = None
    ) -> Progress:
        """Create consistent progress display."""
        columns = [
            SpinnerColumn(style=DisplayStyle.PRIMARY_COLOR),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40) if total else TextColumn(""),
            TaskProgressColumn() if total else TextColumn(""),
            TimeElapsedColumn(),
        ]

        return Progress(*columns, console=self.console, transient=True)

    def _display_processing_summary(self, no_auth_count: int, auth_count: int) -> None:
        """Display processing strategy summary."""
        strategy_text = (
            f"[{DisplayStyle.INFO_COLOR}]📋 Processing Strategy:[/{DisplayStyle.INFO_COLOR}]\n"
            f"  [green]🔓 Non-authenticated services: {no_auth_count} groups[/green]\n"
            f"  [yellow]🔒 Authenticated services: {auth_count} groups[/yellow]\n"
            f"  [{DisplayStyle.DIM_COLOR}]⚡ Optimized order for maximum efficiency[/{DisplayStyle.DIM_COLOR}]"
        )

        strategy_panel = Panel(
            strategy_text,
            title="Processing Plan",
            border_style=DisplayStyle.INFO_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )
        self.console.print(strategy_panel)

    def process_tag(self, tag: FelicaStandard) -> None:
        """Process a FeliCa tag with refined display and extract all data."""
        if not isinstance(tag, FelicaStandard):
            error_panel = Panel(
                f"[{DisplayStyle.ERROR_COLOR}]❌ Invalid Tag Type[/{DisplayStyle.ERROR_COLOR}]\n"
                f"Expected: FeliCa Standard\nReceived: {type(tag).__name__}",
                title="Error",
                border_style=DisplayStyle.ERROR_COLOR,
                box=DisplayStyle.PANEL_BOX,
            )
            self.console.print(error_panel)
            return

        # Show connection status
        self._show_connection_status(tag)

        # Get system codes with progress
        with self._show_processing_progress(
            "🔍 Discovering system codes..."
        ) as progress:
            discovery_task = progress.add_task("Scanning...", total=None)
            system_codes = tag.request_system_code()
            progress.update(
                discovery_task, description=f"Found {len(system_codes)} system(s)"
            )
            time.sleep(0.5)  # Brief pause to show completion

        if not system_codes:
            self.console.print(
                f"[{DisplayStyle.WARNING_COLOR}]⚠️  No system codes found[/{DisplayStyle.WARNING_COLOR}]"
            )
            return

        # Process each system
        for system_idx, system_code in enumerate(system_codes, 1):
            self.console.print(f"\n{'='*60}")
            self.console.print(
                f"[bold {DisplayStyle.ACCENT_COLOR}]Processing System {system_idx}/{len(system_codes)}[/bold {DisplayStyle.ACCENT_COLOR}]"
            )

            # Initialize tag for this system
            polling_result = tag.polling(system_code)
            idm, pmm = polling_result[:2]
            tag.idm = idm
            tag.pmm = pmm
            tag.sys = system_code

            # Initialize components
            key_manager = KeyManager(self.keys_file)
            tag_reader = TagReader(tag)
            service_processor = ServiceProcessor(tag)

            # Load keys
            keys = key_manager.load_keys_for_system(system_code)

            # Discover areas and services
            with self._show_processing_progress(
                "🔍 Analyzing system structure..."
            ) as progress:
                analysis_task = progress.add_task("Discovering...", total=None)
                areas, services = tag_reader.discover_areas_and_services()
                progress.update(
                    analysis_task,
                    description=f"Found {len(areas)} areas, {len(services)} services",
                )
                time.sleep(0.3)

            # Show system overview
            overview_panel = self._create_system_overview_panel(
                system_code, len(keys), len(areas), len(services)
            )
            self.console.print(overview_panel)

            # Get key versions
            with self._show_processing_progress(
                "🔐 Retrieving key versions..."
            ) as progress:
                key_task = progress.add_task("Querying...", total=None)
                key_versions = tag_reader.get_key_versions(system_code, areas, services)
                progress.update(key_task, description="Key versions retrieved")
                time.sleep(0.2)

            # Display detailed information
            self.display.show_system_key_version(system_code, key_versions)
            self.display.show_areas_table(areas, key_versions)

            # Process services
            service_groups = service_processor.group_overlapped_services(services)

            if service_groups:
                # Show service tree
                service_tree = self.display.create_service_tree(
                    service_groups, key_versions
                )
                self.console.print(service_tree)

                # Show processing strategy
                no_auth_groups, auth_groups = optimize_service_processing_order(
                    service_groups
                )
                self._display_processing_summary(len(no_auth_groups), len(auth_groups))

                # Process services with enhanced progress tracking
                results = []
                total_groups = len(service_groups)

                with self._show_processing_progress(
                    "🔄 Processing services...", total_groups
                ) as progress:
                    process_task = progress.add_task(
                        "Processing...", total=total_groups
                    )

                    successful = 0
                    failed = 0

                    # Process non-authenticated services first
                    for group_idx, service_group in enumerate(no_auth_groups, 1):
                        progress.update(
                            process_task,
                            description=f"Processing non-auth group {group_idx}/{len(no_auth_groups)}...",
                        )

                        tag_reader.reset_authentication()
                        result = service_processor.process_service_group(
                            service_group, areas, keys
                        )
                        results.append(result)

                        if result.success:
                            successful += 1
                        else:
                            failed += 1
                        progress.advance(process_task)

                    # Process authenticated services
                    for group_idx, service_group in enumerate(auth_groups, 1):
                        progress.update(
                            process_task,
                            description=f"Processing auth group {group_idx}/{len(auth_groups)}...",
                        )

                        tag_reader.reset_authentication()
                        result = service_processor.process_service_group(
                            service_group, areas, keys
                        )
                        results.append(result)

                        if result.success:
                            successful += 1
                        else:
                            failed += 1
                        progress.advance(process_task)

                    progress.update(process_task, description="✅ Processing complete!")

                # Sort and display results
                results.sort(key=lambda r: r.primary_service_code)
                self.display.display_service_results(results)

                # Calculate and display enhanced summary
                total_blocks = sum(r.block_count for r in results)
                total_time = sum(r.processing_time for r in results)
                processing_time = time.time() - self.start_time

                enhanced_summary = self._create_enhanced_summary(
                    successful, failed, total_blocks, total_time, processing_time
                )
                self.console.print(enhanced_summary)
            else:
                self.console.print(
                    f"[{DisplayStyle.WARNING_COLOR}]⚠️  No services found in this system[/{DisplayStyle.WARNING_COLOR}]"
                )

    def _create_enhanced_summary(
        self,
        successful: int,
        failed: int,
        total_blocks: int,
        total_time: float,
        processing_time: float,
    ) -> Panel:
        """Create an enhanced summary panel with comprehensive statistics."""
        total_services = successful + failed
        success_rate = (successful / total_services * 100) if total_services > 0 else 0

        # Determine border color based on success rate
        if success_rate >= 90:
            border_color = DisplayStyle.SUCCESS_COLOR
            status_icon = "🎉"
            status_text = "Excellent"
        elif success_rate >= 75:
            border_color = DisplayStyle.PRIMARY_COLOR
            status_icon = "✅"
            status_text = "Good"
        elif success_rate >= 50:
            border_color = DisplayStyle.WARNING_COLOR
            status_icon = "⚠️"
            status_text = "Partial"
        else:
            border_color = DisplayStyle.ERROR_COLOR
            status_icon = "❌"
            status_text = "Poor"

        summary_text = (
            f"[bold {DisplayStyle.SUCCESS_COLOR}]{status_icon} Processing Complete - {status_text} Results[/bold {DisplayStyle.SUCCESS_COLOR}]\n\n"
            f"[{DisplayStyle.SUCCESS_COLOR}]✅ Successful Services:[/{DisplayStyle.SUCCESS_COLOR}] {successful}\n"
            f"[{DisplayStyle.ERROR_COLOR}]❌ Failed Services:[/{DisplayStyle.ERROR_COLOR}] {failed}\n"
            f"[{DisplayStyle.PRIMARY_COLOR}]📊 Success Rate:[/{DisplayStyle.PRIMARY_COLOR}] {success_rate:.1f}%\n"
            f"[{DisplayStyle.ACCENT_COLOR}]💾 Total Blocks Read:[/{DisplayStyle.ACCENT_COLOR}] {total_blocks:,}\n"
            f"[{DisplayStyle.INFO_COLOR}]⚡ Service Processing Time:[/{DisplayStyle.INFO_COLOR}] {total_time:.2f}s\n"
            f"[{DisplayStyle.WARNING_COLOR}]🕐 Total Session Time:[/{DisplayStyle.WARNING_COLOR}] {processing_time:.2f}s\n"
            f"[{DisplayStyle.DIM_COLOR}]📈 Average per Service:[/{DisplayStyle.DIM_COLOR}] "
            f"{(total_time/total_services):.2f}s"
            if total_services > 0
            else "N/A"
        )

        return Panel(
            summary_text,
            title="[bold]📈 Final Summary[/bold]",
            border_style=border_color,
            box=DisplayStyle.HEADER_BOX,
        )


def create_on_connect_callback(keys_file: str):
    """Create a callback function with the specified keys file."""

    def on_connect(tag: Tag) -> None:
        """Enhanced callback function when a tag is connected."""
        try:
            dumper = FelicaDumper(keys_file)
            if isinstance(tag, FelicaStandard):
                dumper.process_tag(tag)
            else:
                error_panel = Panel(
                    f"[{DisplayStyle.ERROR_COLOR}]❌ Unsupported Tag Type[/{DisplayStyle.ERROR_COLOR}]\n"
                    f"This application only supports FeliCa Standard tags.\n"
                    f"Detected: {type(tag).__name__}",
                    title="Tag Error",
                    border_style=DisplayStyle.ERROR_COLOR,
                    box=DisplayStyle.PANEL_BOX,
                )
                console.print(error_panel)
        except Exception as e:
            error_panel = Panel(
                f"[{DisplayStyle.ERROR_COLOR}]💥 Unexpected Error[/{DisplayStyle.ERROR_COLOR}]\n"
                f"Error: {str(e)}\n"
                f"Please check your NFC connection and try again.",
                title="System Error",
                border_style=DisplayStyle.ERROR_COLOR,
                box=DisplayStyle.PANEL_BOX,
            )
            console.print(error_panel)

    return on_connect


def main() -> None:
    """Main entry point for the FeliCa Dumper CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="FeliCa Dumper - Extract data from FeliCa cards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Use default keys.csv file
  %(prog)s --keys mykeys.csv  # Use custom keys file
  %(prog)s -k /path/to/keys   # Use keys from specific path
        """,
    )
    parser.add_argument(
        "--keys",
        "-k",
        default="keys.csv",
        help="Path to the keys CSV file (default: keys.csv)",
        metavar="FILE",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="FeliCa Dumper v1.0.0",
    )

    args = parser.parse_args()

    # Display enhanced main header
    header_panel = Panel(
        Align.center(
            f"[bold {DisplayStyle.PRIMARY_COLOR}]🎯 FeliCa Dumper v1.0[/bold {DisplayStyle.PRIMARY_COLOR}]\n"
            f"[{DisplayStyle.INFO_COLOR}]FeliCa Card Data Extraction Tool[/{DisplayStyle.INFO_COLOR}]\n"
            f"[{DisplayStyle.DIM_COLOR}]Place your FeliCa card on the reader...[/{DisplayStyle.DIM_COLOR}]"
        ),
        box=DisplayStyle.HEADER_BOX,
        border_style=DisplayStyle.PRIMARY_COLOR,
        padding=(1, 2),
    )
    console.print(header_panel)

    # Show configuration
    config_panel = Panel(
        f"[{DisplayStyle.INFO_COLOR}]🔧 Configuration:[/{DisplayStyle.INFO_COLOR}]\n"
        f"  Keys file: [bold]{args.keys}[/bold]\n"
        f"  NFC Interface: USB\n"
        f"  Supported frequencies: 212F, 424F",
        title="Setup",
        border_style=DisplayStyle.INFO_COLOR,
        box=DisplayStyle.PANEL_BOX,
    )
    console.print(config_panel)

    # Create callback with the specified keys file
    on_connect_callback = create_on_connect_callback(args.keys)

    try:
        with nfc.ContactlessFrontend("usb") as clf:
            console.print(
                f"[{DisplayStyle.SUCCESS_COLOR}]🔌 NFC reader initialized successfully[/{DisplayStyle.SUCCESS_COLOR}]"
            )
            console.print(
                f"[{DisplayStyle.WARNING_COLOR}]⏳ Waiting for FeliCa card...[/{DisplayStyle.WARNING_COLOR}]"
            )

            clf.connect(
                rdwr={
                    "targets": ["212F", "424F"],
                    "on-startup": lambda target: target,
                    "on-connect": on_connect_callback,
                }
            )
    except Exception as e:
        error_panel = Panel(
            f"[{DisplayStyle.ERROR_COLOR}]💥 Failed to initialize NFC reader[/{DisplayStyle.ERROR_COLOR}]\n"
            f"Error: {str(e)}\n\n"
            f"[{DisplayStyle.INFO_COLOR}]Troubleshooting:[/{DisplayStyle.INFO_COLOR}]\n"
            f"• Check if NFC reader is connected\n"
            f"• Verify USB permissions\n"
            f"• Try running with sudo (Linux/macOS)",
            title="Initialization Error",
            border_style=DisplayStyle.ERROR_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )
        console.print(error_panel)


if __name__ == "__main__":
    main()
