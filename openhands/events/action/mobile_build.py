"""Mobile Build Action for the agent to build mobile applications."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from openhands.core.schema import ActionType
from openhands.events.action.action import Action, ActionSecurityRisk


@dataclass
class MobileBuildAction(Action):
    """Action to build mobile apps using React Native/Expo."""

    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    thought: str = ''
    action: str = ActionType.MOBILE_BUILD
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk = ActionSecurityRisk.LOW

    @property
    def message(self) -> str:
        return f'Mobile build operation: {self.operation} with params: {self.params}'

    def __str__(self) -> str:
        ret = '**MobileBuildAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'OPERATION: {self.operation}\n'
        ret += f'PARAMS: {self.params}'
        return ret
