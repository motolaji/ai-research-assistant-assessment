import pytest
from pathlib import Path
from app.data_store import DataStore
from app.governance import (
    GovernanceContext,
    SmallCellSuppressionPolicy,
    RoleBasedAccessPolicy,
    ProjectAccessPolicy,
    build_policy_chain,
)

store = DataStore(Path("mock-data"))

def test_small_cell_suppression_below_threshold():
    policy = SmallCellSuppressionPolicy(threshold=5)
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS002"})
    result = policy.apply({"count": 2, "rows": []}, ctx)
    assert result["suppressed"] is True
    assert "small_cell_suppression" in ctx.policies_fired

def test_small_cell_suppression_at_boundary_passes():
    policy = SmallCellSuppressionPolicy(threshold=5)
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS001"})
    result = policy.apply({"count": 5, "rows": []}, ctx)
    assert "suppressed" not in result

def test_role_based_allows_unrestricted_without_identity():
    policy = RoleBasedAccessPolicy()
    dataset = store.get_dataset_by_id("DS001")  # unrestricted
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS001"}, dataset=dataset)
    result = policy.apply({"count": 18}, ctx)
    assert "denied" not in result

def test_role_based_denies_researcher_on_restricted():
    policy = RoleBasedAccessPolicy()
    dataset = store.get_dataset_by_id("DS005")  # restricted
    researcher = {"username": "alice", "role": "Researcher"}
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS005"}, dataset=dataset, researcher=researcher)
    result = policy.apply({"count": 3}, ctx)
    assert result["denied"] is True

def test_role_based_allows_admin_on_restricted():
    policy = RoleBasedAccessPolicy()
    dataset = store.get_dataset_by_id("DS005")
    admin = {"username": "admin", "role": "Platform Administrator"}
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS005"}, dataset=dataset, researcher=admin)
    result = policy.apply({"count": 3}, ctx)
    assert "denied" not in result

def test_project_access_allows_own_project():
    policy = ProjectAccessPolicy(store)
    alice = {"username": "alice", "role": "Researcher", "projects": ["PRJ007", "PRJ018"]}
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS007"}, researcher=alice)
    result = policy.apply({"count": 12644}, ctx)
    assert "denied" not in result

def test_project_access_denies_other_project():
    policy = ProjectAccessPolicy(store)
    alice = {"username": "alice", "role": "Researcher", "projects": ["PRJ007", "PRJ018"]}
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS001"}, researcher=alice)
    result = policy.apply({"count": 45405}, ctx)
    assert result["denied"] is True

def test_project_access_skipped_without_identity():
    policy = ProjectAccessPolicy(store)
    ctx = GovernanceContext(tool_name="execute_query", args={"dataset_id": "DS001"}, researcher=None)
    assert policy.applies_to(ctx) is False