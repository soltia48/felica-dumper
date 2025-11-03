"""Main CLI interface for FeliCa Dumper."""

import argparse
import time

import nfc
from nfc.tag import Tag
from nfc.tag.tt3_sony import FelicaStandard
from rich.console import Console, Group
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.table import Table

from .core import KeyManager, TagReader, ServiceProcessor
from .models import ServiceResult
from .ui import DisplayManager, TextOutputManager, SystemExportData
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

    def __init__(self, keys_file: str = "keys.csv", output_file: str | None = None):
        self.console = console
        self.display = DisplayManager(console)
        self.keys_file = keys_file
        self.output_file = output_file
        self.text_output = TextOutputManager(output_file) if output_file else None
        self.start_time = time.time()

    @staticmethod
    def _info_table(
        rows: list[tuple[str, str]], label_style: str = DisplayStyle.DIM_COLOR
    ) -> Table:
        """Create a small table for key/value information."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style=label_style, justify="right", no_wrap=True)
        table.add_column(style="white")
        for label, value in rows:
            table.add_row(label, value)
        return table

    def _show_connection_status(
        self,
        tag: FelicaStandard,
        idm: bytes,
        pmm: bytes,
    ) -> None:
        """Display enhanced connection status."""
        idm_hex = idm.hex().upper()
        pmm_hex = pmm.hex().upper()
        connection_rows = [
            ("Status", f"[{DisplayStyle.SUCCESS_COLOR}]Connected[/]"),
            ("Product", f"[bold]{tag.product}[/bold]"),
            ("IDm", idm_hex),
            ("PMm", pmm_hex),
            ("Connected", time.strftime("%H:%M:%S")),
        ]

        connection_panel = Panel(
            self._info_table(connection_rows),
            title="Connection Status",
            border_style=DisplayStyle.SUCCESS_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )
        self.console.print(connection_panel)

    def _create_system_overview_panel(
        self, system_code: int, keys_count: int, areas_count: int, services_count: int
    ) -> Panel:
        """Create an enhanced system overview panel."""
        overview_rows = [
            ("System code", f"[bold]0x{system_code:04X}[/bold]"),
            ("Keys available", str(keys_count)),
            ("Areas discovered", str(areas_count)),
            ("Services found", str(services_count)),
        ]

        return Panel(
            self._info_table(overview_rows, label_style=DisplayStyle.ACCENT_COLOR),
            title=f"System 0x{system_code:04X}",
            border_style=DisplayStyle.ACCENT_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )

    def _show_processing_progress(
        self, description: str, total: int | None = None
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

    def process_tag(self, tag: FelicaStandard) -> None:
        """Process a FeliCa tag with refined display and extract all data."""
        if not isinstance(tag, FelicaStandard):
            error_panel = Panel(
                Group(
                    Align.left(
                        f"[{DisplayStyle.ERROR_COLOR}]Invalid tag type detected[/{DisplayStyle.ERROR_COLOR}]"
                    ),
                    Align.left("Expected: FeliCa Standard"),
                    Align.left(f"Received: {type(tag).__name__}"),
                ),
                title="Error",
                border_style=DisplayStyle.ERROR_COLOR,
                box=DisplayStyle.PANEL_BOX,
            )
            self.console.print(error_panel)
            return

        # Get system codes with progress
        with self._show_processing_progress("Discovering system codes") as progress:
            discovery_task = progress.add_task("Scanning...", total=None)
            system_codes = tag.request_system_code()
            progress.update(
                discovery_task, description=f"Found {len(system_codes)} system(s)"
            )
            time.sleep(0.5)  # Brief pause to show completion

        if not system_codes:
            self.console.print(
                Panel(
                    "No system codes found on this tag.",
                    title="Scan Result",
                    border_style=DisplayStyle.WARNING_COLOR,
                    box=DisplayStyle.PANEL_BOX,
                )
            )
            return

        # Get IDm and PMm from the first system for display
        first_system_code = system_codes[0]
        polling_result = tag.polling(first_system_code)
        idm, pmm = polling_result[:2]

        # Show connection status with IDm and PMm
        self._show_connection_status(tag, idm, pmm)

        # Process each system
        for system_idx, system_code in enumerate(system_codes, 1):
            self.console.print()
            self.console.rule(
                f"System {system_idx}/{len(system_codes)}",
                style=DisplayStyle.ACCENT_COLOR,
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
                "Analyzing system structure"
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
            with self._show_processing_progress("Retrieving key versions") as progress:
                key_task = progress.add_task("Querying...", total=None)
                key_versions = tag_reader.get_key_versions(system_code, areas, services)
                progress.update(key_task, description="Key versions retrieved")
                time.sleep(0.2)

            # Process services
            service_groups = service_processor.group_overlapped_services(services)
            issue_id_value = None
            issue_parameter_value = None

            if service_groups:
                no_auth_groups, auth_groups = optimize_service_processing_order(
                    service_groups
                )

                # Process services with enhanced progress tracking
                results = []
                total_groups = len(service_groups)

                with self._show_processing_progress(
                    "Processing services", total_groups
                ) as progress:
                    process_task = progress.add_task(
                        "Processing...", total=total_groups
                    )

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

                        progress.advance(process_task)

                    progress.update(process_task, description="Processing complete")

                # Sort and display results
                results.sort(key=lambda r: r.primary_service_code)
                issue_id_value = self._extract_identifier(results, "issue_id")
                issue_parameter_value = self._extract_identifier(
                    results, "issue_parameter"
                )
                idi_hex = self._format_identifier(issue_id_value)
                pmi_hex = self._format_identifier(issue_parameter_value)
                service_tree = self.display.create_service_tree(
                    system_code,
                    areas,
                    service_groups,
                    key_versions,
                    service_results=results,
                    identifiers={
                        "idm": idm.hex().upper(),
                        "pmm": pmm.hex().upper(),
                        "idi": idi_hex,
                        "pmi": pmi_hex,
                    },
                )
                self.console.print(service_tree)

                # Write to text file if output is specified
                if self.text_output:
                    export_data = SystemExportData(
                        system_code=system_code,
                        idm=idm,
                        pmm=pmm,
                        idi=issue_id_value,
                        pmi=issue_parameter_value,
                        keys_file=self.keys_file,
                        keys_count=len(keys),
                        areas_count=len(areas),
                        services_count=len(services),
                        service_groups=service_groups,
                        areas=areas,
                        key_versions=key_versions,
                        results=results,
                    )
                    self.text_output.write_system_data(export_data)
            else:
                self.console.print(
                    Panel(
                        "No readable services were discovered for this system.",
                        title="Services",
                        border_style=DisplayStyle.WARNING_COLOR,
                        box=DisplayStyle.PANEL_BOX,
                    )
                )

                # Write to text file even if no services found
                if self.text_output:
                    export_data = SystemExportData(
                        system_code=system_code,
                        idm=idm,
                        pmm=pmm,
                        idi=issue_id_value,
                        pmi=issue_parameter_value,
                        keys_file=self.keys_file,
                        keys_count=len(keys),
                        areas_count=len(areas),
                        services_count=0,
                        service_groups=[],
                        areas=areas,
                        key_versions=key_versions,
                        results=[],
                    )
                    self.text_output.write_system_data(export_data)

        # Save text output file after processing all systems
        if self.text_output:
            try:
                self.text_output.save_to_file()
                output_path = self.text_output.get_output_path()
                success_panel = Panel(
                    Group(
                        Align.left(
                            f"[{DisplayStyle.SUCCESS_COLOR}]Results saved to text file[/{DisplayStyle.SUCCESS_COLOR}]"
                        ),
                        Align.left(
                            f"[{DisplayStyle.INFO_COLOR}]Path: {output_path}[/{DisplayStyle.INFO_COLOR}]"
                        ),
                    ),
                    title="Text Output",
                    border_style=DisplayStyle.SUCCESS_COLOR,
                    box=DisplayStyle.PANEL_BOX,
                )
                self.console.print(success_panel)
            except Exception as e:
                error_panel = Panel(
                    Group(
                        Align.left(
                            f"[{DisplayStyle.ERROR_COLOR}]Failed to save text output[/{DisplayStyle.ERROR_COLOR}]"
                        ),
                        Align.left(f"[{DisplayStyle.DIM_COLOR}]Error: {str(e)}[/]"),
                    ),
                    title="Output Error",
                    border_style=DisplayStyle.ERROR_COLOR,
                    box=DisplayStyle.PANEL_BOX,
                )
                self.console.print(error_panel)

    @staticmethod
    def _extract_identifier(results: list[ServiceResult], attribute: str):
        """Return the first non-empty identifier from processed service results."""
        for result in results:
            value = getattr(result.used_keys, attribute, None)
            if value:
                return value
        return None

    @staticmethod
    def _format_identifier(value) -> str | None:
        """Format identifier bytes or strings as uppercase hex."""
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.hex().upper()
        if isinstance(value, str):
            return value.upper()
        # Fallback: try to interpret as bytes-like
        try:
            return bytes(value).hex().upper()  # type: ignore[arg-type]
        except Exception:
            return str(value).upper()


def create_on_connect_callback(keys_file: str, output_file: str | None = None):
    """Create a callback function with the specified keys file and output file."""

    def on_connect(tag: Tag) -> None:
        """Enhanced callback function when a tag is connected."""
        try:
            dumper = FelicaDumper(keys_file, output_file)
            if isinstance(tag, FelicaStandard):
                dumper.process_tag(tag)
            else:
                error_panel = Panel(
                    Group(
                        Align.left(
                            f"[{DisplayStyle.ERROR_COLOR}]Unsupported tag type detected[/{DisplayStyle.ERROR_COLOR}]"
                        ),
                        Align.left(
                            "This application only supports FeliCa Standard tags."
                        ),
                        Align.left(f"Detected: {type(tag).__name__}"),
                    ),
                    title="Tag Error",
                    border_style=DisplayStyle.ERROR_COLOR,
                    box=DisplayStyle.PANEL_BOX,
                )
                console.print(error_panel)
        except Exception as e:
            error_panel = Panel(
                Group(
                    Align.left(
                        f"[{DisplayStyle.ERROR_COLOR}]Unexpected error during processing[/{DisplayStyle.ERROR_COLOR}]"
                    ),
                    Align.left(f"[{DisplayStyle.DIM_COLOR}]Error: {str(e)}[/]"),
                    Align.left("Please check your NFC connection and try again."),
                ),
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
  %(prog)s                              # Use default keys.csv file
  %(prog)s --keys mykeys.csv            # Use custom keys file
  %(prog)s -k /path/to/keys             # Use keys from specific path
  %(prog)s -o results.txt               # Save results to text file
  %(prog)s -k mykeys.csv -o output.txt  # Use custom keys and save to file
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
        "--output",
        "-o",
        help="Path to output text file for results (optional)",
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
            "\n".join(
                [
                    f"[bold {DisplayStyle.PRIMARY_COLOR}]FeliCa Dumper v1.0[/bold {DisplayStyle.PRIMARY_COLOR}]",
                    f"[{DisplayStyle.INFO_COLOR}]FeliCa card data extraction tool[/{DisplayStyle.INFO_COLOR}]",
                    f"[{DisplayStyle.DIM_COLOR}]Place your FeliCa card on the reader to begin[/{DisplayStyle.DIM_COLOR}]",
                ]
            )
        ),
        box=DisplayStyle.HEADER_BOX,
        border_style=DisplayStyle.PRIMARY_COLOR,
        padding=(1, 2),
    )
    console.print(header_panel)

    # Show configuration using a compact table
    config_table = Table.grid(padding=(0, 1))
    config_table.add_column(
        style=DisplayStyle.INFO_COLOR, justify="right", no_wrap=True
    )
    config_table.add_column(style="white")
    config_table.add_row("Keys file", f"[bold]{args.keys}[/bold]")
    config_table.add_row("NFC interface", "USB")
    config_table.add_row("Supported modes", "212F, 424F")
    if args.output:
        config_table.add_row("Output file", f"[bold]{args.output}[/bold]")
    config_panel = Panel(
        config_table,
        title="Configuration",
        border_style=DisplayStyle.INFO_COLOR,
        box=DisplayStyle.PANEL_BOX,
    )
    console.print(config_panel)

    # Create callback with the specified keys file and output file
    on_connect_callback = create_on_connect_callback(args.keys, args.output)

    try:
        with nfc.ContactlessFrontend("usb") as clf:
            console.print(
                f"[{DisplayStyle.SUCCESS_COLOR}]NFC reader initialized successfully[/{DisplayStyle.SUCCESS_COLOR}]"
            )
            console.print(f"[{DisplayStyle.DIM_COLOR}]Waiting for FeliCa card...[/]")

            clf.connect(
                rdwr={
                    "targets": ["212F", "424F"],
                    "on-startup": lambda target: target,
                    "on-connect": on_connect_callback,
                }
            )
    except Exception as e:
        error_panel = Panel(
            Group(
                Align.left(
                    f"[{DisplayStyle.ERROR_COLOR}]Failed to initialize NFC reader[/{DisplayStyle.ERROR_COLOR}]"
                ),
                Align.left(f"[{DisplayStyle.DIM_COLOR}]Error: {str(e)}[/]"),
                Align.left(
                    f"[{DisplayStyle.INFO_COLOR}]Troubleshooting steps:[/{DisplayStyle.INFO_COLOR}]"
                ),
                Align.left("- Confirm the NFC reader is connected"),
                Align.left("- Verify USB permissions"),
                Align.left("- Retry with elevated privileges if required"),
            ),
            title="Initialization Error",
            border_style=DisplayStyle.ERROR_COLOR,
            box=DisplayStyle.PANEL_BOX,
        )
        console.print(error_panel)


if __name__ == "__main__":
    main()
