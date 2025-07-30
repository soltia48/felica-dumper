"""Formatting utilities for UI display."""

from ..models import NO_KEY_VALUE


class KeyVersionFormatter:
    """Formats key version information for display."""

    @staticmethod
    def format_key_version(result) -> str:
        """Format key version result consistently.

        Args:
            result: Key version result (int for v1, tuple for v2, or None for failed)

        Returns:
            Formatted string for display
        """
        if result is None:
            return "[red]Failed to retrieve[/red]"

        if isinstance(result, tuple):
            # v2 result: (aes_key, des_key)
            aes_key, des_key = result

            # Format AES key
            aes_display = (
                "[dim]AES:No key[/dim]"
                if aes_key == NO_KEY_VALUE
                else f"[green]AES:0x{aes_key:04X}[/green]"
            )

            # Format DES key
            if des_key is None:
                des_display = "[dim]DES:No key[/dim]"
            elif des_key == NO_KEY_VALUE:
                des_display = "[dim]DES:No key[/dim]"
            else:
                des_display = f"[blue]DES:0x{des_key:04X}[/blue]"

            return f"{aes_display}/{des_display}"

        elif isinstance(result, int):
            # v1 result
            if result == NO_KEY_VALUE:
                return "[dim]DES:No key[/dim]"
            else:
                return f"[blue]DES:0x{result:04X}[/blue]"

        else:
            return "[red]Failed to retrieve[/red]"

    @staticmethod
    def format_service_codes(service_codes: list[int]) -> str:
        """Format service codes for display.

        Args:
            service_codes: List of service codes

        Returns:
            Formatted string
        """
        if len(service_codes) == 1:
            return f"0x{service_codes[0]:04X}"
        else:
            return " & ".join([f"0x{sc:04X}" for sc in service_codes])

    @staticmethod
    def format_area_range(area_start: int, area_end: int) -> str:
        """Format area range for display.

        Args:
            area_start: Start of area range
            area_end: End of area range

        Returns:
            Formatted string
        """
        return f"0x{area_start:04X}--0x{area_end:04X}"

    @staticmethod
    def format_key_info(key_info, show_version: bool = True) -> str:
        """Format key info for display.

        Args:
            key_info: KeyInfo object
            show_version: Whether to show version information

        Returns:
            Formatted string
        """
        base = f"[cyan]0x{key_info.node_id:04X}[/cyan]"
        if show_version:
            base += f"[dim](v{key_info.version})[/dim]"
        return base
