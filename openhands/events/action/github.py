"""GitHub Action for the agent to interact with GitHub API."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from openhands.core.schema import ActionType
from openhands.events.action.action import Action, ActionSecurityRisk


@dataclass
class GitHubAction(Action):
    """Action to interact with GitHub: search repos, read code, create PRs, etc."""

    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    thought: str = ''
    action: str = ActionType.GITHUB
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk = ActionSecurityRisk.LOW

    @property
    def message(self) -> str:
        return f'GitHub operation: {self.operation} with params: {self.params}'

    def __str__(self) -> str:
        ret = '**GitHubAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'OPERATION: {self.operation}\n'
        ret += f'PARAMS: {self.params}'
        return ret
