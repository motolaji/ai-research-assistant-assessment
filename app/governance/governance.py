from app.config import settings
from dataclasses import dataclass, field

from app.datastore import DataStore


@dataclass
class GovernanceContext:
    tool_name: str
    args: dict
    dataset: dict | None = None
    researcher: dict | None = None
    trace_id: str = ""
    policies_fired: list[str] = field(default_factory=list)

class GovernancePolicy:
    name = "base"


    def applies_to(self, context: GovernanceContext) -> bool:
        raise NotImplementedError
    
    def apply(self, result: dict, context: GovernanceContext) -> dict:
        raise NotImplementedError
    
class SmallCellSuppressionPolicy(GovernancePolicy):
    name = "small_cell_suppression"

    def __init__(self, threshold: int = settings.cell_threshold):
        self.threshold = threshold

    def applies_to(self, context: GovernanceContext) -> bool:
        return context.tool_name == "execute_query"

    def apply(self, result: dict, context: GovernanceContext) -> dict:
        count = result.get("count")
        if count is not None and count < self.threshold:
            context.policies_fired.append(self.name)
            return {
                "suppressed": True,
                "reason": f"Results suppressed: the analytical result contains fewer than {self.threshold} records.",
                "dataset_id": context.args.get("dataset_id"),
            }
        return result
    
class PolicyChain:
    def __init__(self, policies: list[GovernancePolicy]):
        self.policies = policies

    def apply(self, result: dict, context: GovernanceContext) -> dict:
        for policy in self.policies:
            if policy.applies_to(context):
                result = policy.apply(result, context)
                if result.get("denied"):
                    break   # access denied, stop processing
        return result    
    

class RoleBasedAccessPolicy(GovernancePolicy):
    name = "role_based_access"

    def applies_to(self, context: GovernanceContext) -> bool:
        return context.tool_name == "execute_query"

    def apply(self, result: dict, context: GovernanceContext) -> dict:
        dataset = context.dataset
        if dataset is None or not dataset.get("restricted", False):
            return result                      # nothing to enforce

        researcher = context.researcher
        if researcher is not None and "administrator" in researcher.get("role", "").lower():
            context.policies_fired.append(self.name)   # audit bypass
            return result                      # admin allowed

        context.policies_fired.append(self.name)
        return {                               # deny
            "denied": True,
            "reason": "Access denied: this dataset is restricted and requires administrator access.",
            "dataset_id": context.args.get("dataset_id"),
        }

class ProjectAccessPolicy(GovernancePolicy):
    name = "project_access"

    def __init__(self, store: DataStore):
        self.store = store

    def applies_to(self, context: GovernanceContext) -> bool:
        return context.tool_name == "execute_query" and context.researcher is not None

    def apply(self, result: dict, context: GovernanceContext) -> dict:
        researcher = context.researcher
        role = researcher.get("role", "").lower()

        if "administrator" in role:
            return result  # admins bypass project-level checks

        dataset_id = context.args.get("dataset_id")
        owning_projects = {p["id"] for p in self.store.projects_for_dataset(dataset_id)}
        researcher_projects = set(researcher.get("projects", []))

        if owning_projects & researcher_projects:
            return result  # overlap exists, researcher is assigned to a project using this dataset

        context.policies_fired.append(self.name)
        return {
            "denied": True,
            "reason": (
                f"Access denied: you are not assigned to any project that uses dataset {dataset_id}."
            ),
            "dataset_id": dataset_id,
        }
    
def build_policy_chain(store: DataStore) -> PolicyChain:
    return PolicyChain([
        RoleBasedAccessPolicy(),
        ProjectAccessPolicy(store),
        SmallCellSuppressionPolicy(),
    ])    
