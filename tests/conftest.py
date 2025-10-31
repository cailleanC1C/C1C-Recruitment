"""Pytest configuration for shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest


def _ensure_project_root_on_path(source_file: Path) -> None:
    """Add the repository root to ``sys.path`` when running from subpackages."""

    for candidate in [source_file.parent, *source_file.parents]:
        shared_dir = candidate / "shared"
        if shared_dir.is_dir():
            project_root = str(candidate)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            break


_ensure_project_root_on_path(Path(__file__).resolve())

from shared.testing.environment import apply_required_test_environment

apply_required_test_environment()

_packages_dir = Path(__file__).resolve().parent.parent / "packages"
_coreops_src = _packages_dir / "c1c-coreops" / "src"
if _coreops_src.is_dir() and str(_coreops_src) not in sys.path:
    sys.path.insert(0, str(_coreops_src))


@pytest.fixture
def patch_recruitment_fetch(monkeypatch):
    """Patch recruitment roster fetching for recruiter panel tests."""

    def _to_int(value: Any) -> int:
        try:
            text = str(value).strip()
        except Exception:  # pragma: no cover - defensive conversion
            return 0
        if not text:
            return 0
        try:
            return int(float(text))
        except Exception:
            return 0

    def _apply(
        panel_module: Any,
        payload: Sequence[Sequence[Any] | Mapping[str, Any] | Any],
        *,
        capture: dict[str, Any] | None = None,
    ) -> type:
        col_spots = getattr(panel_module, "COL_E_SPOTS", 4)
        idx_inactives = getattr(panel_module, "IDX_AG_INACTIVES", 32)

        class _FakeRCR:
            _payload = list(payload)

            def __init__(self, row):
                self.row = row
                if isinstance(row, Mapping):
                    row_seq = tuple(row.values())
                else:
                    row_seq = row
                self.open_spots = _to_int(
                    row_seq[col_spots] if len(row_seq) > col_spots else 0
                )
                self.inactives = _to_int(
                    row_seq[idx_inactives] if len(row_seq) > idx_inactives else 0
                )
                self.reserved = 0
                self.roster = (
                    str(row_seq[col_spots]).strip()
                    if len(row_seq) > col_spots and row_seq[col_spots] is not None
                    else ""
                )

            @classmethod
            def fetch_clans(cls, *args: Any, **kwargs: Any):
                return list(cls._payload)

            @classmethod
            def build_records(cls) -> list["_FakeRCR"]:
                records: list[_FakeRCR] = []
                for entry in cls._payload:
                    if isinstance(entry, cls):
                        records.append(entry)
                    else:
                        records.append(cls(entry))
                return records

        async def _fake_fetch(*, force: bool = False):
            if capture is not None:
                capture["called"] = True
                capture["force"] = force
            return _FakeRCR.build_records()

        monkeypatch.setattr(panel_module, "RecruitmentClanRecord", _FakeRCR, raising=True)
        monkeypatch.setattr(
            panel_module.roster_search,
            "fetch_roster_records",
            _fake_fetch,
            raising=True,
        )
        return _FakeRCR

    return _apply
