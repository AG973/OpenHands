"""Skill registry — central management of loaded skills.

Provides skill discovery by trigger, name, and tag. Manages the lifecycle
of skills including activation and deactivation per session.
"""

from openhands.core.logger import openhands_logger as logger
from openhands.skills.skill_format import Skill
from openhands.skills.skill_loader import SkillLoader


class SkillRegistry:
    """Central registry for managing loaded skills.

    Provides lookup by name, trigger matching, and active skill tracking.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}  # name -> Skill
        self._active_skills: set[str] = set()  # Currently active skill names

    def register(self, skill: Skill) -> None:
        """Register a skill in the registry."""
        if not skill.name:
            logger.warning('Cannot register skill without a name')
            return
        self._skills[skill.name] = skill
        logger.debug(f'Registered skill: {skill.name}')

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry."""
        if name in self._skills:
            del self._skills[name]
            self._active_skills.discard(name)
            return True
        return False

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def load_from_loader(self, loader: SkillLoader) -> int:
        """Load all skills from a SkillLoader and register them.

        Returns:
            Number of skills loaded
        """
        skills = loader.load_all()
        for skill in skills:
            self.register(skill)
        return len(skills)

    def find_by_trigger(self, text: str) -> list[Skill]:
        """Find skills that match a trigger in the given text.

        Args:
            text: Text to search for triggers

        Returns:
            List of matching skills, sorted by priority (highest first)
        """
        matches: list[Skill] = []
        for skill in self._skills.values():
            if skill.matches_trigger(text) is not None:
                matches.append(skill)

        # Sort by priority (descending)
        matches.sort(key=lambda s: s.metadata.priority, reverse=True)
        return matches

    def find_by_tag(self, tag: str) -> list[Skill]:
        """Find skills that have a specific tag."""
        return [
            s for s in self._skills.values()
            if tag.lower() in [t.lower() for t in s.metadata.tags]
        ]

    def activate(self, name: str) -> bool:
        """Mark a skill as active for the current session."""
        if name in self._skills:
            self._active_skills.add(name)
            return True
        return False

    def deactivate(self, name: str) -> None:
        """Deactivate a skill."""
        self._active_skills.discard(name)

    def get_active_skills(self) -> list[Skill]:
        """Get all currently active skills."""
        return [
            self._skills[name]
            for name in self._active_skills
            if name in self._skills
        ]

    def get_all_skills(self) -> list[Skill]:
        """Get all registered skills."""
        return list(self._skills.values())

    @property
    def count(self) -> int:
        return len(self._skills)

    def get_prompt_context(self) -> str:
        """Get all active skills formatted for prompt injection."""
        active = self.get_active_skills()
        if not active:
            return ''

        parts = ['# Active Skills\n']
        for skill in active:
            parts.append(skill.to_prompt_context())
            parts.append('')

        return '\n'.join(parts)
