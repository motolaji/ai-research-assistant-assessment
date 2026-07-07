from app.config import settings
from dataclasses import dataclass, field


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