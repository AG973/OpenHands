"""Mobile app building operations execution handler.

Executes mobile app build operations using React Native/Expo CLI tools.
"""

import json
import os
import subprocess
from typing import Any

from openhands.core.logger import openhands_logger as logger


def _run_command(cmd: list[str], cwd: str | None = None, timeout: int = 120) -> dict[str, Any]:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Command timed out after {timeout} seconds'}
    except FileNotFoundError:
        return {'error': f'Command not found: {cmd[0]}. You may need to install it first.'}
    except Exception as e:
        return {'error': str(e)}


def _check_cli(cli_name: str) -> bool:
    """Check if a CLI tool is installed."""
    result = _run_command(['which', cli_name], timeout=5)
    return result.get('success', False)


def create_project(project_name: str, template: str = 'blank', project_path: str = '') -> dict[str, Any]:
    """Create a new Expo/React Native project."""
    if not project_path:
        project_path = f'/workspace/{project_name}'

    if not _check_cli('npx'):
        return {'error': 'npx not found. Install Node.js first.'}

    template_map = {
        'blank': 'blank',
        'tabs': 'tabs',
        'drawer': 'blank',
        'stack': 'blank',
        'ecommerce': 'blank',
        'social': 'blank',
        'chat': 'blank',
    }
    expo_template = template_map.get(template, 'blank')

    result = _run_command(
        ['npx', 'create-expo-app', project_name, '--template', expo_template],
        cwd=os.path.dirname(project_path),
        timeout=180,
    )
    if result.get('success'):
        return {'success': True, 'path': project_path, 'template': template, 'message': f'Created Expo project {project_name}'}
    return result


def install_dependencies(project_path: str) -> dict[str, Any]:
    """Install project dependencies."""
    result = _run_command(['npm', 'install'], cwd=project_path, timeout=180)
    if result.get('success'):
        return {'success': True, 'message': 'Dependencies installed'}
    return result


def add_package(project_path: str, package_name: str) -> dict[str, Any]:
    """Add a package to the project."""
    result = _run_command(['npx', 'expo', 'install', package_name], cwd=project_path, timeout=60)
    if result.get('success'):
        return {'success': True, 'package': package_name, 'message': f'Added {package_name}'}
    return result


def start_dev_server(project_path: str) -> dict[str, Any]:
    """Start the Expo development server."""
    return {
        'message': f'To start the dev server, run: cd {project_path} && npx expo start',
        'instructions': 'The dev server will run on port 8081. Scan the QR code with Expo Go on your device.',
    }


def build_android(project_path: str, build_type: str = 'apk') -> dict[str, Any]:
    """Build Android APK/AAB using EAS."""
    if not _check_cli('npx'):
        return {'error': 'npx not found.'}
    profile = 'preview' if build_type == 'apk' else 'production'
    result = _run_command(
        ['npx', 'eas-cli', 'build', '--platform', 'android', '--profile', profile, '--non-interactive'],
        cwd=project_path,
        timeout=600,
    )
    if result.get('success'):
        return {'success': True, 'platform': 'android', 'build_type': build_type}
    return result


def build_ios(project_path: str) -> dict[str, Any]:
    """Build iOS app using EAS."""
    if not _check_cli('npx'):
        return {'error': 'npx not found.'}
    result = _run_command(
        ['npx', 'eas-cli', 'build', '--platform', 'ios', '--profile', 'preview', '--non-interactive'],
        cwd=project_path,
        timeout=600,
    )
    if result.get('success'):
        return {'success': True, 'platform': 'ios'}
    return result


def build_web(project_path: str) -> dict[str, Any]:
    """Build the web version."""
    result = _run_command(['npx', 'expo', 'export', '--platform', 'web'], cwd=project_path, timeout=120)
    if result.get('success'):
        return {'success': True, 'platform': 'web', 'output': f'{project_path}/dist'}
    return result


def run_tests(project_path: str) -> dict[str, Any]:
    """Run the test suite."""
    result = _run_command(['npm', 'test', '--', '--watchAll=false'], cwd=project_path, timeout=120)
    return result


def execute_mobile_build_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a mobile build operation and return (content_string, result_data)."""
    try:
        project_path = params.get('project_path', '/workspace/mobile-app')

        if operation == 'create_project':
            result = create_project(
                params.get('project_name', 'my-app'),
                params.get('template', 'blank'),
                project_path,
            )
        elif operation == 'install_dependencies':
            result = install_dependencies(project_path)
        elif operation == 'add_package':
            result = add_package(project_path, params.get('package_name', ''))
        elif operation == 'start_dev_server':
            result = start_dev_server(project_path)
        elif operation == 'build_android':
            result = build_android(project_path, params.get('build_type', 'apk'))
        elif operation == 'build_ios':
            result = build_ios(project_path)
        elif operation == 'build_web':
            result = build_web(project_path)
        elif operation == 'run_tests':
            result = run_tests(project_path)
        elif operation == 'generate_component':
            result = {'message': f'Use the file editor to create component {params.get("component_name", "")} in {project_path}/src/components/'}
        elif operation == 'generate_screen':
            result = {'message': f'Use the file editor to create screen {params.get("component_name", "")} in {project_path}/src/screens/'}
        elif operation == 'preview_qr':
            result = {'message': f'Run: cd {project_path} && npx expo start --qr to get a QR code for Expo Go'}
        elif operation == 'eas_build':
            platform = params.get('platform', 'all')
            profile = params.get('build_profile', 'preview')
            result = _run_command(
                ['npx', 'eas-cli', 'build', '--platform', platform, '--profile', profile, '--non-interactive'],
                cwd=project_path, timeout=600,
            )
        elif operation == 'eas_submit_android':
            result = _run_command(['npx', 'eas-cli', 'submit', '--platform', 'android', '--non-interactive'], cwd=project_path, timeout=300)
        elif operation == 'eas_submit_ios':
            result = _run_command(['npx', 'eas-cli', 'submit', '--platform', 'ios', '--non-interactive'], cwd=project_path, timeout=300)
        elif operation == 'publish_update':
            result = _run_command(['npx', 'eas-cli', 'update', '--non-interactive'], cwd=project_path, timeout=120)
        else:
            result = {'error': f'Unknown mobile build operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Mobile build operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
