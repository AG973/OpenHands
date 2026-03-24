"""Website Build Action for the agent to build web applications."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from openhands.core.schema import ActionType
from openhands.events.action.action import Action, ActionSecurityRisk


@dataclass
class WebsiteBuildAction(Action):
    """Action to build websites/web apps using modern frameworks."""

    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    thought: str = ''
    action: str = ActionType.WEBSITE_BUILD
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk = ActionSecurityRisk.LOW

    @property
    def message(self) -> str:
        return f'Website build operation: {self.operation} with params: {self.params}'

    def __str__(self) -> str:
        ret = '**WebsiteBuildAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'OPERATION: {self.operation}\n'
        ret += f'PARAMS: {self.params}'
        return ret
