"""Mobile app building operations execution handler.

Executes mobile app build operations using React Native/Expo CLI tools.
Supports full build pipeline: project creation, local Android builds (Gradle),
cloud builds (EAS), automated UI testing (Maestro), cloud device testing
(Appetize.io), and app store submission.
"""

import json
import os
import subprocess
from typing import Any

import requests

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


# ============================================================
# EAS Configuration
# ============================================================


def setup_eas_config(project_path: str, app_name: str = '', android_package: str = '', ios_bundle: str = '') -> dict[str, Any]:
    """Generate eas.json and configure EAS Build for the project."""
    eas_config = {
        'cli': {'version': '>= 12.0.0'},
        'build': {
            'development': {
                'developmentClient': True,
                'distribution': 'internal',
            },
            'preview': {
                'distribution': 'internal',
                'android': {'buildType': 'apk'},
            },
            'production': {},
        },
        'submit': {
            'production': {
                'android': {'serviceAccountKeyPath': './google-services.json', 'track': 'internal'},
                'ios': {'appleId': '', 'ascAppId': '', 'appleTeamId': ''},
            },
        },
    }

    eas_path = os.path.join(project_path, 'eas.json')
    try:
        with open(eas_path, 'w') as f:
            json.dump(eas_config, f, indent=2)

        app_json_path = os.path.join(project_path, 'app.json')
        if os.path.exists(app_json_path):
            with open(app_json_path) as f:
                app_config = json.load(f)

            if app_name:
                app_config.setdefault('expo', {})['name'] = app_name
                app_config.setdefault('expo', {})['slug'] = app_name.lower().replace(' ', '-')
            if android_package:
                app_config.setdefault('expo', {}).setdefault('android', {})['package'] = android_package
            if ios_bundle:
                app_config.setdefault('expo', {}).setdefault('ios', {})['bundleIdentifier'] = ios_bundle

            with open(app_json_path, 'w') as f:
                json.dump(app_config, f, indent=2)

        return {
            'success': True,
            'eas_json': eas_path,
            'message': 'EAS configuration created. Run `npx eas-cli build:configure` to complete setup.',
            'next_steps': [
                'Set EXPO_TOKEN environment variable for CI builds',
                'Run `npx eas-cli build --platform android --profile preview` for Android APK',
                'Run `npx eas-cli build --platform ios --profile preview` for iOS build',
            ],
        }
    except Exception as e:
        return {'error': f'Failed to create EAS config: {e}'}


# ============================================================
# Build Operations
# ============================================================


def build_android(project_path: str, build_type: str = 'apk') -> dict[str, Any]:
    """Build Android APK/AAB using local Gradle (if SDK available) or EAS Build (cloud)."""
    if not _check_cli('npx'):
        return {'error': 'npx not found.'}

    # Try local Gradle build first if Android SDK is available
    android_home = os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', ''))
    gradle_wrapper = os.path.join(project_path, 'android', 'gradlew')

    if android_home and os.path.exists(gradle_wrapper):
        return _build_android_local(project_path, build_type)

    # Fall back to EAS cloud build
    return _build_android_eas(project_path, build_type)


def _build_android_local(project_path: str, build_type: str = 'apk') -> dict[str, Any]:
    """Build Android APK locally using Gradle."""
    gradle_wrapper = os.path.join(project_path, 'android', 'gradlew')
    os.chmod(gradle_wrapper, 0o755)

    gradle_task = 'assembleRelease' if build_type == 'apk' else 'bundleRelease'
    result = _run_command(
        [gradle_wrapper, gradle_task],
        cwd=os.path.join(project_path, 'android'),
        timeout=600,
    )

    if result.get('success'):
        if build_type == 'apk':
            output_path = os.path.join(project_path, 'android', 'app', 'build', 'outputs', 'apk', 'release', 'app-release.apk')
        else:
            output_path = os.path.join(project_path, 'android', 'app', 'build', 'outputs', 'bundle', 'release', 'app-release.aab')

        return {
            'success': True,
            'platform': 'android',
            'build_type': build_type,
            'build_method': 'local_gradle',
            'output_path': output_path,
            'message': f'Android {build_type.upper()} built locally via Gradle',
        }
    return result


def _build_android_eas(project_path: str, build_type: str = 'apk') -> dict[str, Any]:
    """Build Android APK/AAB using EAS Build (cloud — no local SDK required)."""
    profile = 'preview' if build_type == 'apk' else 'production'
    result = _run_command(
        ['npx', 'eas-cli', 'build', '--platform', 'android', '--profile', profile, '--non-interactive'],
        cwd=project_path,
        timeout=600,
    )
    if result.get('success'):
        return {
            'success': True,
            'platform': 'android',
            'build_type': build_type,
            'build_method': 'eas_cloud',
            'message': f'Android {build_type.upper()} built via EAS Cloud Build',
        }
    return result


def build_ios(project_path: str) -> dict[str, Any]:
    """Build iOS app using EAS Build (cloud — no Mac required)."""
    if not _check_cli('npx'):
        return {'error': 'npx not found.'}
    result = _run_command(
        ['npx', 'eas-cli', 'build', '--platform', 'ios', '--profile', 'preview', '--non-interactive'],
        cwd=project_path,
        timeout=600,
    )
    if result.get('success'):
        return {'success': True, 'platform': 'ios', 'build_method': 'eas_cloud'}
    return result


def build_web(project_path: str) -> dict[str, Any]:
    """Build the web version."""
    result = _run_command(['npx', 'expo', 'export', '--platform', 'web'], cwd=project_path, timeout=120)
    if result.get('success'):
        return {'success': True, 'platform': 'web', 'output': f'{project_path}/dist'}
    return result


# ============================================================
# Testing — Maestro UI Testing (iOS + Android)
# ============================================================


def setup_maestro(project_path: str) -> dict[str, Any]:
    """Install Maestro CLI and create initial test flow directory."""
    if _check_cli('maestro'):
        version_result = _run_command(['maestro', '--version'], timeout=10)
        return {
            'success': True,
            'already_installed': True,
            'version': version_result.get('stdout', '').strip(),
            'message': 'Maestro is already installed',
        }

    install_result = _run_command(
        ['bash', '-c', 'curl -Ls "https://get.maestro.mobile.dev" | bash'],
        timeout=120,
    )

    if not install_result.get('success'):
        return {'error': f'Failed to install Maestro: {install_result.get("stderr", install_result.get("error", ""))}'}

    flows_dir = os.path.join(project_path, '.maestro')
    os.makedirs(flows_dir, exist_ok=True)

    return {
        'success': True,
        'maestro_installed': True,
        'flows_dir': flows_dir,
        'message': 'Maestro installed. Create YAML flow files in .maestro/ directory.',
        'next_steps': [
            'Create test flow files in .maestro/ (e.g., login-flow.yaml)',
            'Run `maestro test .maestro/` to execute all flows',
            'Use `maestro studio` for interactive test building',
        ],
    }


def create_maestro_flow(project_path: str, flow_name: str, flow_steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a Maestro YAML test flow file.

    Args:
        project_path: Path to the project
        flow_name: Name of the flow (e.g., 'login', 'signup', 'checkout')
        flow_steps: List of step dicts. If None, creates a basic launch + screenshot flow.
    """
    flows_dir = os.path.join(project_path, '.maestro')
    os.makedirs(flows_dir, exist_ok=True)

    if flow_steps is None:
        flow_content = f"""# {flow_name} test flow
appId: com.example.app  # Update with your app's bundle ID
---
- launchApp
- assertVisible: "Welcome"
- takeScreenshot: {flow_name}_screenshot
"""
    else:
        lines = [f'# {flow_name} test flow', "appId: com.example.app  # Update with your app's bundle ID", '---']
        for step in flow_steps:
            if isinstance(step, dict):
                for action, value in step.items():
                    if isinstance(value, dict):
                        lines.append(f'- {action}:')
                        for k, v in value.items():
                            lines.append(f'    {k}: "{v}"')
                    else:
                        lines.append(f'- {action}: "{value}"')
            elif isinstance(step, str):
                lines.append(f'- {step}')
        flow_content = '\n'.join(lines) + '\n'

    flow_path = os.path.join(flows_dir, f'{flow_name}.yaml')
    try:
        with open(flow_path, 'w') as f:
            f.write(flow_content)
        return {
            'success': True,
            'flow_path': flow_path,
            'message': f'Created Maestro flow: {flow_path}',
        }
    except Exception as e:
        return {'error': f'Failed to create flow: {e}'}


def run_maestro_test(project_path: str, flow_name: str = '', platform: str = 'android') -> dict[str, Any]:
    """Run Maestro UI tests against the app on a connected device/emulator.

    Tests both iOS and Android separately using the same YAML flows.

    Args:
        project_path: Path to the project
        flow_name: Specific flow to run (empty = run all flows in .maestro/)
        platform: Target platform (android or ios)
    """
    if not _check_cli('maestro'):
        return {'error': 'Maestro is not installed. Run setup_maestro first.'}

    flows_dir = os.path.join(project_path, '.maestro')
    if not os.path.exists(flows_dir):
        return {'error': f'No .maestro/ directory found at {project_path}. Create test flows first.'}

    if flow_name:
        flow_path = os.path.join(flows_dir, f'{flow_name}.yaml')
        if not os.path.exists(flow_path):
            return {'error': f'Flow file not found: {flow_path}'}
        cmd = ['maestro', 'test', flow_path]
    else:
        cmd = ['maestro', 'test', flows_dir]

    result = _run_command(cmd, cwd=project_path, timeout=300)

    output = result.get('stdout', '') + result.get('stderr', '')
    passed = result.get('success', False)

    return {
        'success': passed,
        'platform': platform,
        'flow': flow_name or 'all',
        'output': output[:5000],
        'message': f'Maestro tests {"PASSED" if passed else "FAILED"} on {platform}',
    }


def run_maestro_studio(project_path: str) -> dict[str, Any]:
    """Start Maestro Studio for interactive visual test building."""
    return {
        'message': f'To start Maestro Studio, run: cd {project_path} && maestro studio',
        'instructions': [
            'Maestro Studio opens a web UI at http://localhost:9999',
            'Use it to visually build test flows by interacting with your app',
            'Flows are saved as YAML files you can commit to your repo',
        ],
    }


# ============================================================
# Cloud Device Testing — Appetize.io
# ============================================================


def upload_to_appetize(app_path: str, platform: str = 'android') -> dict[str, Any]:
    """Upload an APK/IPA to Appetize.io for cloud device testing in browser.

    This lets you test iOS apps without a Mac and Android apps without an emulator.

    Args:
        app_path: Path to the APK (Android) or IPA/ZIP (iOS) file
        platform: 'android' or 'ios'
    """
    api_token = os.environ.get('APPETIZE_API_TOKEN', '')
    if not api_token:
        return {
            'error': 'APPETIZE_API_TOKEN environment variable not set.',
            'instructions': [
                'Sign up at https://appetize.io/',
                'Get your API token from the dashboard',
                'Set APPETIZE_API_TOKEN=<your_token>',
            ],
        }

    if not os.path.exists(app_path):
        return {'error': f'App file not found: {app_path}'}

    try:
        with open(app_path, 'rb') as f:
            resp = requests.post(
                'https://api.appetize.io/v2/apps',
                headers={'Authorization': f'Bearer {api_token}'},
                files={'file': f},
                data={'platform': platform},
                timeout=120,
            )
        resp.raise_for_status()
        data = resp.json()

        public_key = data.get('publicKey', '')
        app_url = f'https://appetize.io/app/{public_key}' if public_key else ''

        return {
            'success': True,
            'public_key': public_key,
            'app_url': app_url,
            'platform': platform,
            'message': f'App uploaded to Appetize.io. Test it at: {app_url}',
        }
    except requests.exceptions.HTTPError as e:
        return {'error': f'Appetize upload failed: {e}', 'status_code': resp.status_code}
    except Exception as e:
        return {'error': f'Appetize upload failed: {e}'}


def get_appetize_embed_url(public_key: str, device: str = '', os_version: str = '') -> dict[str, Any]:
    """Get an embeddable URL for testing an app on Appetize.io.

    Args:
        public_key: Appetize public key from upload
        device: Device model (e.g., 'pixel7', 'iphone15pro')
        os_version: OS version (e.g., '14.0', '17.0')
    """
    params: list[str] = []
    if device:
        params.append(f'device={device}')
    if os_version:
        params.append(f'osVersion={os_version}')

    query_string = '&'.join(params)
    base_url = f'https://appetize.io/embed/{public_key}'
    full_url = f'{base_url}?{query_string}' if query_string else base_url

    return {
        'success': True,
        'embed_url': full_url,
        'app_url': f'https://appetize.io/app/{public_key}',
        'message': 'Appetize embed URL ready. Open in browser to test the app on a virtual device.',
    }


# ============================================================
# Local Emulator/Simulator Operations
# ============================================================


def start_android_emulator(avd_name: str = '') -> dict[str, Any]:
    """Start an Android emulator."""
    android_home = os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', ''))
    if not android_home:
        return {'error': 'ANDROID_HOME/ANDROID_SDK_ROOT not set. Install Android SDK first.'}

    emulator_bin = os.path.join(android_home, 'emulator', 'emulator')
    if not os.path.exists(emulator_bin):
        return {'error': f'Emulator binary not found at {emulator_bin}'}

    if not avd_name:
        list_result = _run_command([emulator_bin, '-list-avds'], timeout=10)
        avds = [a.strip() for a in list_result.get('stdout', '').strip().split('\n') if a.strip()]
        if not avds:
            return {
                'error': 'No AVDs found. Create one first.',
                'instructions': 'Run: sdkmanager "system-images;android-34;google_apis;x86_64" && avdmanager create avd -n test_device -k "system-images;android-34;google_apis;x86_64"',
            }
        avd_name = avds[0]

    subprocess.Popen(
        [emulator_bin, '-avd', avd_name, '-no-window', '-no-audio', '-no-boot-anim'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {
        'success': True,
        'avd': avd_name,
        'message': f'Android emulator starting with AVD: {avd_name}. Wait ~30s for boot.',
        'next_steps': [
            'Run `adb wait-for-device` to wait for emulator to fully boot',
            'Install your APK: `adb install path/to/app.apk`',
            'Run Maestro tests: `maestro test .maestro/`',
        ],
    }


def install_apk_on_device(app_path: str) -> dict[str, Any]:
    """Install an APK on a connected Android device/emulator via ADB."""
    if not _check_cli('adb'):
        return {'error': 'adb not found. Install Android SDK platform-tools.'}

    if not os.path.exists(app_path):
        return {'error': f'APK not found: {app_path}'}

    result = _run_command(['adb', 'install', '-r', app_path], timeout=60)
    if result.get('success'):
        return {'success': True, 'apk': app_path, 'message': 'APK installed on device'}
    return result


# ============================================================
# Standard Operations
# ============================================================


def run_tests(project_path: str) -> dict[str, Any]:
    """Run the project's unit test suite (Jest)."""
    result = _run_command(['npm', 'test', '--', '--watchAll=false'], cwd=project_path, timeout=120)
    return result


# ============================================================
# Main Dispatcher
# ============================================================


def execute_mobile_build_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a mobile build operation and return (content_string, result_data)."""
    try:
        project_path = params.get('project_path', '/workspace/mobile-app')

        # --- Project Setup ---
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
        elif operation == 'setup_eas_config':
            result = setup_eas_config(
                project_path,
                params.get('app_name', ''),
                params.get('android_package', ''),
                params.get('ios_bundle', ''),
            )

        # --- Building ---
        elif operation == 'build_android':
            result = build_android(project_path, params.get('build_type', 'apk'))
        elif operation == 'build_ios':
            result = build_ios(project_path)
        elif operation == 'build_web':
            result = build_web(project_path)
        elif operation == 'eas_build':
            platform = params.get('platform', 'all')
            profile = params.get('build_profile', 'preview')
            result = _run_command(
                ['npx', 'eas-cli', 'build', '--platform', platform, '--profile', profile, '--non-interactive'],
                cwd=project_path, timeout=600,
            )

        # --- Testing: Maestro ---
        elif operation == 'setup_maestro':
            result = setup_maestro(project_path)
        elif operation == 'create_maestro_flow':
            result = create_maestro_flow(
                project_path,
                params.get('flow_name', 'default'),
                params.get('flow_steps'),
            )
        elif operation == 'run_maestro_test':
            result = run_maestro_test(
                project_path,
                params.get('flow_name', ''),
                params.get('platform', 'android'),
            )
        elif operation == 'run_maestro_studio':
            result = run_maestro_studio(project_path)

        # --- Testing: Cloud Devices (Appetize.io) ---
        elif operation == 'upload_to_appetize':
            result = upload_to_appetize(
                params.get('app_path', ''),
                params.get('platform', 'android'),
            )
        elif operation == 'get_appetize_embed_url':
            result = get_appetize_embed_url(
                params.get('public_key', ''),
                params.get('device', ''),
                params.get('os_version', ''),
            )

        # --- Testing: Local Emulator ---
        elif operation == 'start_android_emulator':
            result = start_android_emulator(params.get('avd_name', ''))
        elif operation == 'install_apk_on_device':
            result = install_apk_on_device(params.get('app_path', ''))

        # --- Testing: Unit Tests ---
        elif operation == 'run_tests':
            result = run_tests(project_path)

        # --- Deployment ---
        elif operation == 'eas_submit_android':
            result = _run_command(['npx', 'eas-cli', 'submit', '--platform', 'android', '--non-interactive'], cwd=project_path, timeout=300)
        elif operation == 'eas_submit_ios':
            result = _run_command(['npx', 'eas-cli', 'submit', '--platform', 'ios', '--non-interactive'], cwd=project_path, timeout=300)
        elif operation == 'publish_update':
            result = _run_command(['npx', 'eas-cli', 'update', '--non-interactive'], cwd=project_path, timeout=120)

        # --- Convenience ---
        elif operation == 'generate_component':
            result = {'message': f'Use the file editor to create component {params.get("component_name", "")} in {project_path}/src/components/'}
        elif operation == 'generate_screen':
            result = {'message': f'Use the file editor to create screen {params.get("component_name", "")} in {project_path}/src/screens/'}
        elif operation == 'preview_qr':
            result = {'message': f'Run: cd {project_path} && npx expo start --qr to get a QR code for Expo Go'}
        else:
            result = {'error': f'Unknown mobile build operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Mobile build operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
