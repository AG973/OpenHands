"""Cloud Deploy Action for the agent to deploy to cloud platforms."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from openhands.core.schema import ActionType
from openhands.events.action.action import Action, ActionSecurityRisk


@dataclass
class CloudDeployAction(Action):
    """Action to deploy applications to AWS, GCP, Azure, RunPod, etc."""

    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    thought: str = ''
    action: str = ActionType.CLOUD_DEPLOY
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk = ActionSecurityRisk.MEDIUM

    @property
    def message(self) -> str:
        return f'Cloud deploy operation: {self.operation} with params: {self.params}'

    def __str__(self) -> str:
        ret = '**CloudDeployAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'OPERATION: {self.operation}\n'
        ret += f'PARAMS: {self.params}'
        return ret
