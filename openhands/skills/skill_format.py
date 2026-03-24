"""Skill format — structured skill definition with YAML frontmatter + markdown body.

Skills are markdown files with YAML frontmatter that define:
- Metadata (name, description, triggers, version, author)
- Structured steps/checklists
- Knowledge content

Ported from OpenClaw's skills system patterns.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillMetadata:
    """Metadata from skill frontmatter."""

    name: str = ''
    description: str = ''
    triggers: list[str] = field(default_factory=list)
    version: str = '1.0.0'
    author: str = ''
    tags: list[str] = field(default_factory=list)
    priority: int = 0  # Higher = more important
    enabled: bool = True
    scope: str = 'global'  # 'global', 'workspace', 'user'
    requires: list[str] = field(default_factory=list)  # Dependencies on other skills


@dataclass
class SkillStep:
    """A single step in a skill procedure."""

    index: int
    description: str
    is_optional: bool = False
    is_completed: bool = False
    sub_steps: list['SkillStep'] = field(default_factory=list)


@dataclass
class Skill:
    """A complete skill definition."""

    metadata: SkillMetadata
    content: str  # Full markdown body
    steps: list[SkillStep] = field(default_factory=list)
    source_path: str = ''  # Where this skill was loaded from

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def triggers(self) -> list[str]:
        return self.metadata.triggers

    def matches_trigger(self, text: str) -> str | None:
        """Check if text matches any of this skill's triggers.

        Returns the matched trigger string or None.
        """
        text_lower = text.lower()
        for trigger in self.metadata.triggers:
            if trigger.lower() in text_lower:
                return trigger
        return None

    def to_prompt_context(self) -> str:
        """Format this skill for injection into the agent prompt."""
        parts = [f'## Skill: {self.metadata.name}']
        if self.metadata.description:
            parts.append(f'**Description**: {self.metadata.description}')
        if self.metadata.tags:
            parts.append(f'**Tags**: {", ".join(self.metadata.tags)}')
        parts.append('')
        parts.append(self.content)
        return '\n'.join(parts)


def parse_skill(text: str, source_path: str = '') -> Skill:
    """Parse a skill from markdown text with optional YAML frontmatter.

    Supports:
    - YAML frontmatter between --- delimiters
    - Numbered step lists (1. Step one, 2. Step two)
    - Optional steps marked with (optional) suffix
    - Sub-steps as indented lists

    Args:
        text: Raw markdown text of the skill file
        source_path: File path this was loaded from

    Returns:
        Parsed Skill object
    """
    metadata = SkillMetadata()
    content = text

    # Extract YAML frontmatter if present
    frontmatter_match = re.match(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        text,
        re.DOTALL,
    )
    if frontmatter_match:
        frontmatter_text = frontmatter_match.group(1)
        content = frontmatter_match.group(2)
        metadata = _parse_frontmatter(frontmatter_text)

    # If no name in frontmatter, try to extract from first heading
    if not metadata.name:
        heading_match = re.match(r'^#\s+(.+)$', content, re.MULTILINE)
        if heading_match:
            metadata.name = heading_match.group(1).strip()

    # Extract steps from content
    steps = _extract_steps(content)

    return Skill(
        metadata=metadata,
        content=content,
        steps=steps,
        source_path=source_path,
    )


def _parse_frontmatter(text: str) -> SkillMetadata:
    """Parse YAML-like frontmatter into SkillMetadata.

    Uses simple key: value parsing to avoid PyYAML dependency.
    """
    metadata = SkillMetadata()
    current_key = ''
    current_list: list[str] = []

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Check for list continuation
        if line.startswith('- ') and current_key:
            current_list.append(line[2:].strip())
            continue

        # Save accumulated list if we were building one
        if current_list and current_key:
            _set_metadata_field(metadata, current_key, current_list)
            current_list = []

        # Parse key: value
        colon_idx = line.find(':')
        if colon_idx > 0:
            key = line[:colon_idx].strip()
            value = line[colon_idx + 1:].strip()
            current_key = key

            if value.startswith('[') and value.endswith(']'):
                # Inline list: [item1, item2]
                items = [
                    item.strip().strip('"').strip("'")
                    for item in value[1:-1].split(',')
                    if item.strip()
                ]
                _set_metadata_field(metadata, key, items)
                current_key = ''
            elif value:
                _set_metadata_field(metadata, key, value)
                current_key = ''
            # else: value is on next lines as list

    # Handle trailing list
    if current_list and current_key:
        _set_metadata_field(metadata, current_key, current_list)

    return metadata


def _set_metadata_field(
    metadata: SkillMetadata, key: str, value: str | list[str]
) -> None:
    """Set a metadata field from parsed frontmatter."""
    key_lower = key.lower().replace('-', '_').replace(' ', '_')

    if key_lower == 'name' and isinstance(value, str):
        metadata.name = value
    elif key_lower == 'description' and isinstance(value, str):
        metadata.description = value
    elif key_lower == 'version' and isinstance(value, str):
        metadata.version = value
    elif key_lower == 'author' and isinstance(value, str):
        metadata.author = value
    elif key_lower == 'scope' and isinstance(value, str):
        metadata.scope = value
    elif key_lower == 'priority' and isinstance(value, str):
        try:
            metadata.priority = int(value)
        except ValueError:
            pass
    elif key_lower == 'enabled' and isinstance(value, str):
        metadata.enabled = value.lower() in ('true', 'yes', '1')
    elif key_lower in ('triggers', 'trigger'):
        if isinstance(value, list):
            metadata.triggers = value
        elif isinstance(value, str):
            metadata.triggers = [value]
    elif key_lower in ('tags', 'tag'):
        if isinstance(value, list):
            metadata.tags = value
        elif isinstance(value, str):
            metadata.tags = [value]
    elif key_lower in ('requires', 'dependencies'):
        if isinstance(value, list):
            metadata.requires = value
        elif isinstance(value, str):
            metadata.requires = [value]


def _extract_steps(content: str) -> list[SkillStep]:
    """Extract numbered steps from markdown content."""
    steps: list[SkillStep] = []
    step_pattern = re.compile(r'^(\d+)\.\s+(.+)$', re.MULTILINE)

    for match in step_pattern.finditer(content):
        index = int(match.group(1))
        description = match.group(2).strip()

        is_optional = '(optional)' in description.lower()
        if is_optional:
            description = re.sub(r'\s*\(optional\)\s*', '', description, flags=re.IGNORECASE).strip()

        steps.append(
            SkillStep(
                index=index,
                description=description,
                is_optional=is_optional,
            )
        )

    return steps
