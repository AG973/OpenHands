"""Observations for the new agent tools (GitHub, Cloud Deploy, Discord, etc.)."""

from dataclasses import dataclass, field
from typing import Any

from openhands.core.schema import ObservationType
from openhands.events.observation.observation import Observation


@dataclass
class GitHubObservation(Observation):
    """Observation from a GitHub operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.GITHUB

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'GitHub {self.operation}: {truncated}'


@dataclass
class CloudDeployObservation(Observation):
    """Observation from a cloud deployment operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.CLOUD_DEPLOY

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'Cloud Deploy {self.operation}: {truncated}'


@dataclass
class DiscordObservation(Observation):
    """Observation from a Discord operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.DISCORD

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'Discord {self.operation}: {truncated}'


@dataclass
class MobileBuildObservation(Observation):
    """Observation from a mobile build operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.MOBILE_BUILD

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'Mobile Build {self.operation}: {truncated}'


@dataclass
class WebsiteBuildObservation(Observation):
    """Observation from a website build operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.WEBSITE_BUILD

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'Website Build {self.operation}: {truncated}'


@dataclass
class ServerManagementObservation(Observation):
    """Observation from a server management operation."""

    operation: str = ''
    result_data: dict[str, Any] = field(default_factory=dict)
    observation: str = ObservationType.SERVER_MANAGEMENT

    @property
    def message(self) -> str:
        truncated = self.content[:200] + '...' if len(self.content) > 200 else self.content
        return f'Server Management {self.operation}: {truncated}'
