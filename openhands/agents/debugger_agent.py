"""Debugger Agent — analyzes test failures and produces fix strategies.

The debugger activates when the TesterAgent reports failures. It analyzes
error messages, stack traces, and test output to determine root cause
and suggest targeted fixes.

Patterns extracted from:
    - GPT-Pilot: Debugger agent with LLM-powered trace analysis
    - OpenHands: StuckDetector + error classification
    - Cline: Iterative error-fix-retry loop
"""

from __future__ import annotations

from typing import Any

from openhands.agents.base_role import AgentRole, RoleContext, RoleName, RoleOutput
from openhands.core.logger import openhands_logger as logger


class DebuggerAgent(AgentRole):
    """Analyzes failures and produces targeted fix strategies.

    The debugger:
    - Parses error messages and stack traces
    - Classifies error types (syntax, runtime, logic, import, config)
    - Searches error memory for similar past failures
    - Suggests specific fixes with file + line references
    - Prioritizes fixes by likelihood of success
    """

    # Error classification patterns
    ERROR_PATTERNS: dict[str, list[str]] = {
        'import_error': ['ImportError', 'ModuleNotFoundError', 'cannot find module'],
        'syntax_error': ['SyntaxError', 'IndentationError', 'unexpected token'],
        'type_error': ['TypeError', 'AttributeError', 'is not a function'],
        'runtime_error': ['RuntimeError', 'ValueError', 'KeyError', 'IndexError'],
        'assertion_error': ['AssertionError', 'assert', 'expected', 'to equal'],
        'connection_error': ['ConnectionError', 'TimeoutError', 'ECONNREFUSED'],
        'permission_error': ['PermissionError', 'EACCES', 'permission denied'],
        'config_error': ['ConfigError', 'missing required', 'invalid configuration'],
    }

    @property
    def role_name(self) -> RoleName:
        return RoleName.DEBUGGER

    @property
    def description(self) -> str:
        return (
            'Analyzes test failures and errors, classifies root causes, '
            'searches error memory for past solutions, and produces fix strategies.'
        )

    def execute(self, context: RoleContext) -> RoleOutput:
        """Analyze failures and produce fix strategies."""
        # Collect all error information
        error_info = self._collect_errors(context)

        # Classify the errors
        classified = self._classify_errors(error_info)

        # Search error memory for similar past failures
        memory_matches = self._search_error_memory(classified, context)

        # Generate fix suggestions
        fixes = self._generate_fixes(classified, memory_matches, context)

        # Update context
        context.debug_analysis = self._format_analysis(classified, fixes)
        context.suggested_fixes = fixes

        has_fixes = len(fixes) > 0

        logger.info(
            f'[Debugger] Analyzed {len(error_info)} errors, '
            f'classified {len(classified)} types, '
            f'suggested {len(fixes)} fixes'
        )

        return RoleOutput(
            role=self.role_name,
            success=has_fixes,
            error='' if has_fixes else 'No fix strategies could be generated',
            output_data={
                'error_count': len(error_info),
                'classifications': [c['type'] for c in classified],
                'fix_count': len(fixes),
                'memory_matches': len(memory_matches),
            },
            artifacts=[
                {
                    'type': 'debug_analysis',
                    'name': 'failure_analysis',
                    'content': {
                        'errors': error_info,
                        'classifications': classified,
                        'fixes': fixes,
                    },
                }
            ],
        )

    def _collect_errors(self, context: RoleContext) -> list[dict[str, Any]]:
        """Collect all error information from context."""
        errors: list[dict[str, Any]] = []

        # From failed tests
        if context.failed_tests:
            for test_name in context.failed_tests:
                errors.append({
                    'source': 'test',
                    'test_name': test_name,
                    'output': context.test_output,
                })

        # From test output
        if context.test_output and not context.test_passed:
            errors.append({
                'source': 'test_output',
                'output': context.test_output,
            })

        # From metadata
        if context.metadata.get('last_error'):
            errors.append({
                'source': 'execution',
                'output': context.metadata['last_error'],
            })

        return errors

    def _classify_errors(
        self, errors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Classify errors by type using pattern matching."""
        classified: list[dict[str, Any]] = []

        for error in errors:
            output = error.get('output', '')
            error_type = 'unknown'
            confidence = 0.0

            for err_type, patterns in self.ERROR_PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in output.lower():
                        error_type = err_type
                        confidence = 0.8
                        break
                if error_type != 'unknown':
                    break

            classified.append({
                'type': error_type,
                'confidence': confidence,
                'source': error.get('source', ''),
                'test_name': error.get('test_name', ''),
                'raw_output': output[:500],
            })

        return classified

    def _search_error_memory(
        self,
        classified: list[dict[str, Any]],
        context: RoleContext,
    ) -> list[dict[str, Any]]:
        """Search error memory for similar past failures."""
        matches: list[dict[str, Any]] = []

        for cls in classified:
            error_type = cls['type']
            for memory_entry in context.error_memory:
                if memory_entry.get('error_type') == error_type:
                    matches.append({
                        'current_error': error_type,
                        'past_error': memory_entry,
                        'similarity': 0.7,
                    })

        return matches

    def _generate_fixes(
        self,
        classified: list[dict[str, Any]],
        memory_matches: list[dict[str, Any]],
        context: RoleContext,
    ) -> list[dict[str, Any]]:
        """Generate fix suggestions based on classification and memory."""
        fixes: list[dict[str, Any]] = []

        # Check fix memory first
        for match in memory_matches:
            past = match.get('past_error', {})
            if past.get('fix_applied'):
                fixes.append({
                    'strategy': 'memory_replay',
                    'description': f'Apply known fix from past: {past["fix_applied"]}',
                    'confidence': 0.8,
                    'source': 'fix_memory',
                })

        # Generate type-specific fix suggestions
        for cls in classified:
            error_type = cls['type']

            if error_type == 'import_error':
                fixes.append({
                    'strategy': 'fix_import',
                    'description': 'Fix import path or install missing dependency',
                    'confidence': 0.7,
                    'error_type': error_type,
                })
            elif error_type == 'syntax_error':
                fixes.append({
                    'strategy': 'fix_syntax',
                    'description': 'Fix syntax error in the identified file',
                    'confidence': 0.9,
                    'error_type': error_type,
                })
            elif error_type == 'type_error':
                fixes.append({
                    'strategy': 'fix_types',
                    'description': 'Fix type mismatch or missing attribute',
                    'confidence': 0.6,
                    'error_type': error_type,
                })
            elif error_type == 'assertion_error':
                fixes.append({
                    'strategy': 'fix_logic',
                    'description': 'Fix logic error causing assertion failure',
                    'confidence': 0.5,
                    'error_type': error_type,
                })
            elif error_type == 'config_error':
                fixes.append({
                    'strategy': 'fix_config',
                    'description': 'Fix configuration or environment setup',
                    'confidence': 0.7,
                    'error_type': error_type,
                })
            else:
                fixes.append({
                    'strategy': 'investigate',
                    'description': f'Investigate {error_type} error and apply targeted fix',
                    'confidence': 0.3,
                    'error_type': error_type,
                })

        # Sort by confidence
        fixes.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        return fixes

    def _format_analysis(
        self,
        classified: list[dict[str, Any]],
        fixes: list[dict[str, Any]],
    ) -> str:
        """Format analysis as human-readable text."""
        lines: list[str] = ['## Failure Analysis', '']

        if classified:
            lines.append('### Errors Found')
            for cls in classified:
                lines.append(
                    f'- **{cls["type"]}** (confidence: {cls["confidence"]:.0%}) '
                    f'from {cls["source"]}'
                )
            lines.append('')

        if fixes:
            lines.append('### Suggested Fixes')
            for i, fix in enumerate(fixes, 1):
                lines.append(
                    f'{i}. [{fix["strategy"]}] {fix["description"]} '
                    f'(confidence: {fix.get("confidence", 0):.0%})'
                )
            lines.append('')

        return '\n'.join(lines)
