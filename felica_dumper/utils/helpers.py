"""Helper utility functions."""


def optimize_service_processing_order(
    service_groups: list[list[int]],
) -> tuple[list[list[int]], list[list[int]]]:
    """Optimize service processing order by separating authenticated and non-authenticated services.

    Args:
        service_groups: List of service groups

    Returns:
        Tuple of (no_auth_groups, auth_groups) for optimized processing
    """
    no_auth_groups = []
    auth_groups = []

    for service_group in service_groups:
        has_no_auth = any(sc & 1 for sc in service_group)
        if has_no_auth:
            no_auth_groups.append(service_group)
        else:
            auth_groups.append(service_group)

    return no_auth_groups, auth_groups
