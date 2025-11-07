"""
Import shim for test helpers.

Prefer local implementations in shared/testing/, but if the repository
keeps helpers under modules.shared.testing for historical reasons,
expose them here to satisfy `import shared.testing`.
"""
try:
    # Local helpers colocated here (if present)
    from .helpers import *  # noqa: F401,F403
except Exception:
    # Fallback to modules.shared.testing if that package exists
    try:
        from modules.shared.testing import *  # type: ignore  # noqa: F401,F403
    except Exception:
        # Leave the package importable even if empty; individual tests may not require helpers.
        pass
