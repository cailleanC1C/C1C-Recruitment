"""Recruiter panel cog entrypoint.

Symmetry with `cogs/recruitment_member.py`. This module ensures a stable import
location for recruiter features without changing behavior.
"""
from modules.recruitment.views.recruiter_panel import *  # re-export if needed
# NOTE: This file intentionally does not register new commands here.
# Existing recruiter registration remains where it was; this provides a clear home.
