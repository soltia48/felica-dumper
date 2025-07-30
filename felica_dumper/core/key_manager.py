"""Key management functionality."""

import csv

from rich.console import Console

from ..models import (
    KeyInfo,
    SYSTEM_KEY_NODE_ID,
    ROOT_AREA_KEY_NODE_ID,
    AREA_KEY_THRESHOLD,
)

console = Console()


class KeyManager:
    """Manages FeliCa keys loading and organization."""

    def __init__(self, csv_file: str = "keys.csv"):
        self.csv_file = csv_file
        self._keys_cache: dict[int, dict[int, KeyInfo]] = {}

    def load_keys_for_system(self, system_code: int) -> dict[int, KeyInfo]:
        """Load keys from CSV file for a specific system code.

        Args:
            system_code: System code to filter keys (16-bit integer)

        Returns:
            Dictionary mapping node IDs to KeyInfo objects for the specified system_code
        """
        if system_code in self._keys_cache:
            return self._keys_cache[system_code]

        keys: dict[int, KeyInfo] = {}
        try:
            with open(self.csv_file, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    row_system_code = int(row["system_code"], 16)

                    # Filter by system_code if specified
                    if system_code is not None and row_system_code != system_code:
                        continue

                    node_id = int(row["node"], 16)
                    key_value = bytes.fromhex(row["key"])
                    version = int(row["version"])

                    key_type = self._determine_key_type(node_id)

                    key_info = KeyInfo(
                        node_id=node_id,
                        version=version,
                        key_value=key_value,
                        key_type=key_type,
                    )
                    keys[node_id] = key_info

            self._keys_cache[system_code] = keys

        except FileNotFoundError:
            console.print(f"[yellow]⚠️  Warning: {self.csv_file} not found.[/yellow]")
            return {}
        except Exception as e:
            console.print(f"[red]❌ Error reading {self.csv_file}: {e}[/red]")
            return {}

        return keys

    def _determine_key_type(self, node_id: int) -> str:
        """Determine key type based on node_id.

        Args:
            node_id: The node ID to classify

        Returns:
            Key type string: "system", "area", or "service"
        """
        if node_id == SYSTEM_KEY_NODE_ID:
            return "system"
        elif node_id == ROOT_AREA_KEY_NODE_ID:
            return "area"  # Root area key
        else:
            # Check if it's likely an area key (typically lower values) or service key
            if node_id < AREA_KEY_THRESHOLD:
                return "area"
            else:
                return "service"

    def get_key(self, system_code: int, node_id: int) -> KeyInfo | None:
        """Get a specific key by system code and node ID.

        Args:
            system_code: System code
            node_id: Node ID of the key

        Returns:
            KeyInfo object if found, None otherwise
        """
        keys = self.load_keys_for_system(system_code)
        return keys.get(node_id)

    def has_system_key(self, system_code: int) -> bool:
        """Check if system key exists for the given system code.

        Args:
            system_code: System code to check

        Returns:
            True if system key exists, False otherwise
        """
        keys = self.load_keys_for_system(system_code)
        return SYSTEM_KEY_NODE_ID in keys

    def has_service_key(self, system_code: int, service_code: int) -> bool:
        """Check if service key exists for the given service code.

        Args:
            system_code: System code
            service_code: Service code to check

        Returns:
            True if service key exists, False otherwise
        """
        keys = self.load_keys_for_system(system_code)
        return service_code in keys

    def get_area_keys_for_service(
        self, system_code: int, service_code: int, areas: list
    ) -> list[KeyInfo]:
        """Get area keys that contain the given service code.

        Args:
            system_code: System code
            service_code: Service code
            areas: List of (area_start, area_end) tuples

        Returns:
            List of KeyInfo objects for containing areas
        """
        keys = self.load_keys_for_system(system_code)
        area_keys = []

        for area_start, area_end in areas:
            if area_start <= service_code <= area_end and area_start in keys:
                area_keys.append(keys[area_start])

        return area_keys
