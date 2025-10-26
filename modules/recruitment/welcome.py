"""Shim module preserving import compatibility for the recruitment welcome cog."""

from __future__ import annotations

from cogs.recruitment_welcome import WelcomeBridge, setup, staff_only

__all__ = ["WelcomeBridge", "setup", "staff_only"]
