import os
from typing import Optional


def get_port(env_var: str = "PORT", fallback: int = 10000) -> int:
    """Leaf helper to avoid circular imports. Read PORT (Render/Heroku style)."""
    try:
        val: Optional[str] = os.getenv(env_var)
        return int(val) if val else int(fallback)
    except Exception:
        return int(fallback)
