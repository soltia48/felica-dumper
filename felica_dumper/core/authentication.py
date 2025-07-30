"""FeliCa authentication functionality."""

from rich.console import Console

from nfc.tag.tt3_sony import FelicaStandard, KeyManager
from ..models import KeyInfo, UsedKeys, SYSTEM_KEY_NODE_ID

console = Console()


class AuthenticationHandler:
    """Handles FeliCa authentication operations."""

    def __init__(self, tag: FelicaStandard):
        self.tag = tag

    def authenticate_service(
        self,
        service_code: int,
        areas: list[tuple[int, int]],
        keys: dict[int, KeyInfo],
        used_keys: UsedKeys | None = None,
    ) -> tuple[bool, list[str]]:
        """Authenticate for a service and return success status and messages.

        Args:
            service_code: Service code to authenticate for
            areas: List of (area_start, area_end) tuples
            keys: Dictionary of available keys
            used_keys: Optional UsedKeys object to track used keys

        Returns:
            Tuple of (success, error_messages)
        """
        error_messages = []

        # Find containing areas
        containing_areas = []
        for area_start, area_end in areas:
            if area_start <= service_code <= area_end:
                containing_areas.append((area_start, area_end))

        if not containing_areas:
            error_messages.append(f"  ✗ Service not found in any area")
            return False, error_messages

        containing_areas.sort(key=lambda x: x[0])

        # Check for required keys
        if SYSTEM_KEY_NODE_ID not in keys:
            error_messages.append(
                f"  ✗ System key (0x{SYSTEM_KEY_NODE_ID:04X}) not found"
            )
            return False, error_messages

        if service_code not in keys:
            error_messages.append(f"  ✗ Service key (0x{service_code:04X}) not found")
            return False, error_messages

        # Record used keys
        if used_keys is not None:
            used_keys.authentication_required = True
            used_keys.system_key = keys[SYSTEM_KEY_NODE_ID]
            used_keys.service_keys.append(keys[service_code])

        # Build key chain
        system_key_info = keys[SYSTEM_KEY_NODE_ID]
        area_key_infos = []
        for area_start, area_end in containing_areas:
            if area_start in keys:
                area_key_info = keys[area_start]
                area_key_infos.append(area_key_info)
                if used_keys is not None:
                    used_keys.area_keys.append(area_key_info)
            else:
                error_messages.append(f"  ⚠ No key for area 0x{area_start:04X}")

        service_key_info = keys[service_code]

        # Extract actual key values for authentication
        system_key = system_key_info.key_value
        area_keys = [key_info.key_value for key_info in area_key_infos]
        service_keys = [service_key_info.key_value]

        try:
            # Generate authentication keys
            group_service_key, user_service_key = KeyManager.generate_service_keys(
                system_key, area_keys, service_keys
            )

            # Authenticate
            area_codes = [area[0] for area in containing_areas]
            service_codes = [service_code]

            issue_id, issue_parameter = self.tag.mutual_authentication(
                area_codes, service_codes, group_service_key, user_service_key
            )

            return True, error_messages

        except Exception as e:
            error_messages.append(f"  ✗ Authentication failed: {e}")
            return False, error_messages

    def requires_authentication(self, service_code: int) -> bool:
        """Check if service requires authentication based on service code.

        Args:
            service_code: Service code to check

        Returns:
            True if authentication is required, False otherwise
        """
        # Check if service requires authentication (LSB = 0) or not (LSB = 1)
        return not (service_code & 1)
