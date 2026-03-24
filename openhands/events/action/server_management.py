"""Server Management Action for the agent to manage servers and GPU instances."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from openhands.core.schema import ActionType
from openhands.events.action.action import Action, ActionSecurityRisk


@dataclass
class ServerManagementAction(Action):
    """Action to manage servers, SSH connections, and cloud GPU instances."""

    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    thought: str = ''
    action: str = ActionType.SERVER_MANAGEMENT
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk = ActionSecurityRisk.MEDIUM

    @property
    def message(self) -> str:
        return f'Server management operation: {self.operation} with params: {self.params}'

    def __str__(self) -> str:
        ret = '**ServerManagementAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'OPERATION: {self.operation}\n'
        ret += f'PARAMS: {self.params}'
        return ret
