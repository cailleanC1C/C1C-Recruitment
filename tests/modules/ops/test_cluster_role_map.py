from __future__ import annotations

from modules.ops import cluster_role_map


class DummyMember:
    def __init__(self, mention: str):
        self.mention = mention


class DummyRole:
    def __init__(self, role_id: int, name: str, members: list[DummyMember] | None = None):
        self.id = role_id
        self.name = name
        self.members = members or []


class DummyGuild:
    def __init__(self, name: str, roles: list[DummyRole]):
        self.name = name
        self._roles = {role.id: role for role in roles}

    def get_role(self, role_id: int):  # pragma: no cover - simple mapping
        return self._roles.get(role_id)


def test_parse_role_map_records_filters_invalid_rows():
    rows = [
        {"category": "ClusterLeadership", "role_ID": "123", "role_name": "Lead", "role_description": "Runs it"},
        {"category": "", "role_ID": "456", "role_name": "Missing"},
        {"category": "ClusterSupport", "role_ID": "abc", "role_name": "Helper"},
        {"category": "Recruitment", "role_ID": "789", "role_name": "Recruiter", "role_description": ""},
    ]

    entries = cluster_role_map.parse_role_map_records(rows)

    assert len(entries) == 2
    assert entries[0].category == "ClusterLeadership"
    assert entries[1].category == "Recruitment"
    assert entries[1].role_description == ""


def test_build_role_map_render_renders_categories_and_members():
    entries = [
        cluster_role_map.RoleMapRow(
            category="ClusterLeadership",
            role_id=1,
            sheet_role_name="Lead", 
            role_description="Runs it",
        ),
        cluster_role_map.RoleMapRow(
            category="ClusterSupport",
            role_id=2,
            sheet_role_name="Support", 
            role_description="",
        ),
        cluster_role_map.RoleMapRow(
            category="ClusterSupport",
            role_id=99,
            sheet_role_name="Backup", 
            role_description="Keeps receipts",
        ),
    ]
    guild = DummyGuild(
        "TestGuild",
        [
            DummyRole(1, "Leader", [DummyMember("<@1>")]),
            DummyRole(2, "Shield", []),
        ],
    )

    render = cluster_role_map.build_role_map_render(guild, entries)

    assert "💙 WHO WE ARE" in render.message
    assert "🔥 ClusterLeadership" in render.message
    assert "🛡️ ClusterSupport" in render.message
    assert "**Leader** — Runs it" in render.message
    assert "<@1>" in render.message
    assert "**Shield** — no description set" in render.message
    assert "**Backup** — Keeps receipts" in render.message
    assert "(currently unassigned)" in render.message
    assert render.category_count == 2
    assert render.role_count == 3
    assert render.unassigned_roles == 2
