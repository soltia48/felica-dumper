"""Main CLI interface for FeliCa Dumper."""

import argparse
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
)

from .core import KeyManager, TagReader, ServiceProcessor
from .ui import DisplayManager
from .utils import optimize_service_processing_order

# Initialize Rich console
console = Console()


class FelicaDumper:
    """Main FeliCa Dumper application."""

    def __init__(self, keys_file: str = "keys.csv"):
        self.console = console
        self.display = DisplayManager(console)
        self.keys_file = keys_file

    def process_tag(self, tag: FelicaStandard):
        """Process a FeliCa tag and extract all data."""
        if not isinstance(tag, FelicaStandard):
            self.console.print("[red]❌ Not a FeliCa Standard tag[/red]")
            return

        # Display header
        self.display.show_header(tag.product)

        # Get system codes
        system_codes = tag.request_system_code()

        for system_code in system_codes:
            # Initialize tag for this system
            polling_result = tag.polling(system_code)
            idm, pmm = polling_result[:2]
            tag.idm = idm
            tag.pmm = pmm
            tag.sys = system_code

            # Display system header
            self.display.show_system_header(system_code)

            # Initialize components for this system
            key_manager = KeyManager(self.keys_file)
            tag_reader = TagReader(tag)
            service_processor = ServiceProcessor(tag)

            # Load keys for this specific system code
            keys = key_manager.load_keys_for_system(system_code)

            # Discover areas and services with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                discovery_task = progress.add_task(
                    "🔍 Discovering areas and services...", total=None
                )
                areas, services = tag_reader.discover_areas_and_services()

            # Display system information
            self.display.show_system_info(len(keys), len(areas), len(services))

            # Get key versions with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                key_task = progress.add_task("🔐 Getting key versions...", total=None)
                key_versions = tag_reader.get_key_versions(system_code, areas, services)

            # Display key version information
            self.display.show_system_key_version(system_code, key_versions)
            self.display.show_areas_table(areas, key_versions)

            # Group overlapped services and display
            service_groups = service_processor.group_overlapped_services(services)
            service_tree = self.display.create_service_tree(
                service_groups, key_versions
            )
            self.console.print(service_tree)

            # Optimize service processing order
            no_auth_groups, auth_groups = optimize_service_processing_order(
                service_groups
            )
            self.display.show_processing_order(len(no_auth_groups), len(auth_groups))

            # Process services with progress bar
            results = []
            total_groups = len(service_groups)
            warnings = 0

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("({task.completed}/{task.total})"),
            ) as progress:
                process_task = progress.add_task(
                    "🔄 Processing services...", total=total_groups
                )

                successful = 0
                failed = 0

                # Process non-authenticated services first
                for service_group in no_auth_groups:
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
                for service_group in auth_groups:
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

            # Sort results and display
            results.sort(key=lambda r: r.primary_service_code)
            self.display.display_service_results(results)

            # Calculate totals and display summary
            total_blocks = sum(r.block_count for r in results)
            total_time = sum(r.processing_time for r in results)

            summary_panel = self.display.create_summary_panel(
                successful, failed, total_blocks, total_time, warnings
            )
            self.console.print(summary_panel)


def create_on_connect_callback(keys_file: str):
    """Create a callback function with the specified keys file."""

    def on_connect(tag: Tag):
        """Callback function when a tag is connected."""
        dumper = FelicaDumper(keys_file)
        if isinstance(tag, FelicaStandard):
            dumper.process_tag(tag)
        else:
            console.print("[red]❌ Not a FeliCa Standard tag[/red]")

    return on_connect


def main():
    """Main entry point for the FeliCa Dumper CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="FeliCa Dumper - Extract data from FeliCa cards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--keys",
        "-k",
        default="keys.csv",
        help="Path to the keys CSV file (default: keys.csv)",
    )

    args = parser.parse_args()

    # Display main header
    display = DisplayManager()
    display.show_main_header()

    # Create callback with the specified keys file
    on_connect_callback = create_on_connect_callback(args.keys)

    with nfc.ContactlessFrontend("usb") as clf:
        clf.connect(
            rdwr={
                "targets": ["212F", "424F"],
                "on-startup": lambda target: target,
                "on-connect": on_connect_callback,
            }
        )


if __name__ == "__main__":
    main()
