"""Skill loader — discover and load skills from filesystem directories.

Loads skills from:
1. Global skills: ~/.openhands/skills/
2. Workspace skills: .openhands/skills/ in the workspace root
3. Built-in skills: openhands/skills/builtin/

Ported from OpenClaw's skill loading patterns.
"""

import os
from pathlib import Path

from openhands.core.logger import openhands_logger as logger
from openhands.skills.skill_format import Skill, parse_skill

# Skill file extensions
SKILL_EXTENSIONS = {'.md', '.markdown', '.skill'}

# Default directories
GLOBAL_SKILLS_DIR = os.path.join(str(Path.home()), '.openhands', 'skills')
BUILTIN_SKILLS_DIR = os.path.join(os.path.dirname(__file__), 'builtin')


class SkillLoader:
    """Load skills from multiple directory sources.

    Skills are markdown files with optional YAML frontmatter that define
    reusable procedures, checklists, and knowledge for the agent.
    """

    def __init__(
        self,
        workspace_dir: str | None = None,
        global_skills_dir: str = GLOBAL_SKILLS_DIR,
        builtin_skills_dir: str = BUILTIN_SKILLS_DIR,
        extra_dirs: list[str] | None = None,
    ):
        self._workspace_dir = workspace_dir
        self._global_skills_dir = global_skills_dir
        self._builtin_skills_dir = builtin_skills_dir
        self._extra_dirs = extra_dirs or []

    def load_all(self) -> list[Skill]:
        """Load skills from all configured directories.

        Load order (later entries override earlier on name collision):
        1. Built-in skills
        2. Global user skills (~/.openhands/skills/)
        3. Workspace skills (.openhands/skills/)
        4. Extra directories

        Returns:
            List of loaded Skill objects, deduplicated by name
        """
        skills_by_name: dict[str, Skill] = {}

        # 1. Built-in skills
        for skill in self._load_from_dir(self._builtin_skills_dir, scope='builtin'):
            skills_by_name[skill.name] = skill

        # 2. Global user skills
        for skill in self._load_from_dir(self._global_skills_dir, scope='global'):
            skills_by_name[skill.name] = skill

        # 3. Workspace skills
        if self._workspace_dir:
            workspace_skills_dir = os.path.join(
                self._workspace_dir, '.openhands', 'skills'
            )
            for skill in self._load_from_dir(workspace_skills_dir, scope='workspace'):
                skills_by_name[skill.name] = skill

        # 4. Extra directories
        for extra_dir in self._extra_dirs:
            for skill in self._load_from_dir(extra_dir, scope='extra'):
                skills_by_name[skill.name] = skill

        skills = list(skills_by_name.values())
        logger.info(f'Loaded {len(skills)} skills from all sources')
        return skills

    def load_workspace_skills(self) -> list[Skill]:
        """Load only workspace-scoped skills."""
        if not self._workspace_dir:
            return []
        workspace_skills_dir = os.path.join(
            self._workspace_dir, '.openhands', 'skills'
        )
        return self._load_from_dir(workspace_skills_dir, scope='workspace')

    def load_global_skills(self) -> list[Skill]:
        """Load only global user skills."""
        return self._load_from_dir(self._global_skills_dir, scope='global')

    def _load_from_dir(self, directory: str, scope: str = 'unknown') -> list[Skill]:
        """Load all skill files from a directory.

        Args:
            directory: Path to scan for skill files
            scope: Scope label for loaded skills

        Returns:
            List of parsed Skill objects
        """
        skills: list[Skill] = []

        if not os.path.isdir(directory):
            logger.debug(f'Skills directory does not exist: {directory}')
            return skills

        for root, _dirs, files in os.walk(directory):
            for filename in sorted(files):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SKILL_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                skill = self._load_skill_file(filepath, scope)
                if skill is not None:
                    skills.append(skill)

        logger.debug(f'Loaded {len(skills)} skills from {directory} (scope={scope})')
        return skills

    def _load_skill_file(self, filepath: str, scope: str) -> Skill | None:
        """Load and parse a single skill file.

        Args:
            filepath: Full path to the skill file
            scope: Scope to assign to the skill

        Returns:
            Parsed Skill or None if loading fails
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                logger.debug(f'Skipping empty skill file: {filepath}')
                return None

            skill = parse_skill(content, source_path=filepath)
            skill.metadata.scope = scope

            # If no name was set, use filename
            if not skill.metadata.name:
                skill.metadata.name = os.path.splitext(os.path.basename(filepath))[0]

            if not skill.metadata.enabled:
                logger.debug(f'Skipping disabled skill: {skill.name}')
                return None

            return skill

        except Exception as e:
            logger.warning(f'Failed to load skill from {filepath}: {e}')
            return None
