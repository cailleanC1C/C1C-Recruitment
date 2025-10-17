"""Helper for assigning visibility tiers to commands for dynamic help rendering."""


def tier(level: str):
    """Attach a visibility tier for help rendering ('user', 'staff', 'admin')."""

    def wrapper(cmd):
        cmd._tier = level
        return cmd

    return wrapper
