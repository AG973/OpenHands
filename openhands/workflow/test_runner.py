"""Workflow Test Runner — executes tests as part of the workflow pipeline.

Detects the test framework, runs tests, parses results, and reports
pass/fail with structured output. Used by the execution engine's
TEST phase.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class TestResult:
    """Result of a test execution."""

    passed: bool = False
    total_tests: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    duration_s: float = 0.0
    stdout: str = ''
    stderr: str = ''
    failed_test_names: list[str] = field(default_factory=list)
    framework: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'passed': self.passed,
            'total_tests': self.total_tests,
            'passed_count': self.passed_count,
            'failed_count': self.failed_count,
            'skipped_count': self.skipped_count,
            'error_count': self.error_count,
            'duration_s': self.duration_s,
            'failed_test_names': self.failed_test_names[:20],
            'framework': self.framework,
        }


class WorkflowTestRunner:
    """Executes tests in a repository workspace.

    Usage:
        runner = WorkflowTestRunner("/path/to/repo")
        result = runner.run()
        print(result.passed, result.failed_count)
    """

    def __init__(self, repo_path: str) -> None:
        self._repo_path = os.path.abspath(repo_path)

    def run(
        self,
        test_files: list[str] | None = None,
        framework: str = '',
        timeout_s: int = 300,
    ) -> TestResult:
        """Run tests in the repository.

        Args:
            test_files: Specific test files to run (None = all)
            framework: Force a specific framework (auto-detect if empty)
            timeout_s: Test execution timeout

        Returns:
            TestResult with pass/fail details
        """
        if not framework:
            framework = self._detect_framework()

        if not framework:
            logger.warning('[TestRunner] No test framework detected')
            return TestResult(
                passed=True,
                framework='none',
                stdout='No test framework detected',
            )

        cmd = self._build_command(framework, test_files)
        logger.info(f'[TestRunner] Running: {" ".join(cmd)}')

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            duration = time.time() - start_time

            result = self._parse_result(
                proc.stdout, proc.stderr, proc.returncode, framework
            )
            result.duration_s = duration
            result.framework = framework

            logger.info(
                f'[TestRunner] Tests completed: '
                f'{result.passed_count}/{result.total_tests} passed '
                f'in {duration:.2f}s'
            )
            return result

        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                duration_s=float(timeout_s),
                stderr=f'Tests timed out after {timeout_s}s',
                framework=framework,
            )
        except Exception as e:
            return TestResult(
                passed=False,
                stderr=str(e),
                framework=framework,
            )

    def run_specific(
        self, test_files: list[str], timeout_s: int = 300
    ) -> TestResult:
        """Run specific test files."""
        return self.run(test_files=test_files, timeout_s=timeout_s)

    def _detect_framework(self) -> str:
        """Auto-detect the test framework."""
        # Python
        if os.path.exists(os.path.join(self._repo_path, 'pytest.ini')):
            return 'pytest'
        if os.path.exists(os.path.join(self._repo_path, 'pyproject.toml')):
            try:
                with open(
                    os.path.join(self._repo_path, 'pyproject.toml'), 'r'
                ) as f:
                    if 'pytest' in f.read():
                        return 'pytest'
            except OSError:
                pass
        if os.path.exists(os.path.join(self._repo_path, 'setup.cfg')):
            return 'pytest'

        # JavaScript/TypeScript
        pkg_json = os.path.join(self._repo_path, 'package.json')
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, 'r') as f:
                    content = f.read()
                    if 'vitest' in content:
                        return 'vitest'
                    if 'jest' in content:
                        return 'jest'
                    if 'mocha' in content:
                        return 'mocha'
            except OSError:
                pass

        # Go
        if os.path.exists(os.path.join(self._repo_path, 'go.mod')):
            return 'go-test'

        # Rust
        if os.path.exists(os.path.join(self._repo_path, 'Cargo.toml')):
            return 'cargo-test'

        return ''

    def _build_command(
        self, framework: str, test_files: list[str] | None
    ) -> list[str]:
        """Build the test execution command."""
        if framework == 'pytest':
            cmd = ['python', '-m', 'pytest', '-v', '--tb=short']
            if test_files:
                cmd.extend(test_files)
            return cmd

        if framework == 'jest':
            cmd = ['npx', 'jest', '--verbose']
            if test_files:
                cmd.extend(test_files)
            return cmd

        if framework == 'vitest':
            cmd = ['npx', 'vitest', 'run']
            if test_files:
                cmd.extend(test_files)
            return cmd

        if framework == 'mocha':
            cmd = ['npx', 'mocha']
            if test_files:
                cmd.extend(test_files)
            return cmd

        if framework == 'go-test':
            cmd = ['go', 'test', '-v']
            if test_files:
                cmd.extend(test_files)
            else:
                cmd.append('./...')
            return cmd

        if framework == 'cargo-test':
            cmd = ['cargo', 'test']
            if test_files:
                cmd.extend(test_files)
            return cmd

        return ['echo', f'Unknown framework: {framework}']

    def _parse_result(
        self, stdout: str, stderr: str, return_code: int, framework: str
    ) -> TestResult:
        """Parse test output into a TestResult."""
        result = TestResult(
            passed=return_code == 0,
            stdout=stdout,
            stderr=stderr,
        )

        combined = stdout + stderr

        if framework == 'pytest':
            self._parse_pytest(combined, result)
        elif framework in ('jest', 'vitest'):
            self._parse_jest(combined, result)
        elif framework == 'go-test':
            self._parse_go_test(combined, result)

        return result

    def _parse_pytest(self, output: str, result: TestResult) -> None:
        """Parse pytest output."""
        for line in output.split('\n'):
            line = line.strip()
            if 'passed' in line or 'failed' in line or 'error' in line:
                # Look for summary line like "5 passed, 2 failed"
                import re

                passed_match = re.search(r'(\d+)\s+passed', line)
                failed_match = re.search(r'(\d+)\s+failed', line)
                error_match = re.search(r'(\d+)\s+error', line)
                skipped_match = re.search(r'(\d+)\s+skipped', line)

                if passed_match:
                    result.passed_count = int(passed_match.group(1))
                if failed_match:
                    result.failed_count = int(failed_match.group(1))
                if error_match:
                    result.error_count = int(error_match.group(1))
                if skipped_match:
                    result.skipped_count = int(skipped_match.group(1))

            if line.startswith('FAILED'):
                result.failed_test_names.append(line)

        result.total_tests = (
            result.passed_count
            + result.failed_count
            + result.error_count
            + result.skipped_count
        )

    def _parse_jest(self, output: str, result: TestResult) -> None:
        """Parse Jest/Vitest output."""
        import re

        for line in output.split('\n'):
            tests_match = re.search(
                r'Tests:\s+(\d+)\s+passed(?:,\s+(\d+)\s+failed)?(?:,\s+(\d+)\s+total)?',
                line,
            )
            if tests_match:
                result.passed_count = int(tests_match.group(1) or 0)
                result.failed_count = int(tests_match.group(2) or 0)
                result.total_tests = int(tests_match.group(3) or 0)

            if 'FAIL' in line and '●' not in line:
                result.failed_test_names.append(line.strip())

    def _parse_go_test(self, output: str, result: TestResult) -> None:
        """Parse go test output."""
        for line in output.split('\n'):
            if line.startswith('--- PASS'):
                result.passed_count += 1
            elif line.startswith('--- FAIL'):
                result.failed_count += 1
                result.failed_test_names.append(line.strip())
            elif line.startswith('--- SKIP'):
                result.skipped_count += 1

        result.total_tests = (
            result.passed_count + result.failed_count + result.skipped_count
        )
