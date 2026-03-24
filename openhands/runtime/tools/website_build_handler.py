"""Website building operations execution handler.

Executes website build operations using modern framework CLI tools.
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


def create_project(project_name: str, framework: str = 'nextjs', project_path: str = '') -> dict[str, Any]:
    """Create a new web project using the specified framework."""
    if not project_path:
        project_path = f'/workspace/{project_name}'

    framework_commands: dict[str, list[str]] = {
        'nextjs': ['npx', 'create-next-app@latest', project_name, '--ts', '--eslint', '--app', '--src-dir', '--no-tailwind', '--import-alias', '@/*'],
        'react': ['npx', 'create-vite@latest', project_name, '--template', 'react-ts'],
        'vue': ['npx', 'create-vite@latest', project_name, '--template', 'vue-ts'],
        'svelte': ['npx', 'create-svelte@latest', project_name],
        'astro': ['npx', 'create-astro@latest', project_name, '--template', 'basics', '--no-install', '--no-git'],
        'express': ['npx', 'express-generator', project_name],
        'html': ['mkdir', '-p', project_path],
    }

    cmd = framework_commands.get(framework)
    if not cmd:
        return {'error': f'Unknown framework: {framework}. Supported: {list(framework_commands.keys())}'}

    if framework == 'html':
        os.makedirs(project_path, exist_ok=True)
        # Create basic HTML project
        index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Welcome to {name}</h1>
    <script src="script.js"></script>
</body>
</html>'''.format(name=project_name)
        with open(os.path.join(project_path, 'index.html'), 'w') as f:
            f.write(index_html)
        with open(os.path.join(project_path, 'style.css'), 'w') as f:
            f.write('body { font-family: system-ui; margin: 2rem; }\n')
        with open(os.path.join(project_path, 'script.js'), 'w') as f:
            f.write('console.log("Hello from ' + project_name + '");\n')
        return {'success': True, 'path': project_path, 'framework': 'html'}

    if framework in ('fastapi', 'django', 'flask'):
        return _create_python_project(project_name, framework, project_path)

    parent_dir = os.path.dirname(project_path) or '/workspace'
    os.makedirs(parent_dir, exist_ok=True)
    result = _run_command(cmd, cwd=parent_dir, timeout=180)
    if result.get('success'):
        return {'success': True, 'path': project_path, 'framework': framework, 'message': f'Created {framework} project'}
    return result


def _create_python_project(project_name: str, framework: str, project_path: str) -> dict[str, Any]:
    """Create a Python web project (FastAPI, Django, Flask)."""
    os.makedirs(project_path, exist_ok=True)

    if framework == 'fastapi':
        main_py = '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="{name}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    return {{"message": "Welcome to {name}"}}

@app.get("/health")
async def health():
    return {{"status": "healthy"}}
'''.format(name=project_name)
        requirements = 'fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\n'

    elif framework == 'flask':
        main_py = '''from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def root():
    return jsonify(message="Welcome to {name}")

@app.route("/health")
def health():
    return jsonify(status="healthy")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
'''.format(name=project_name)
        requirements = 'flask>=3.0.0\n'

    elif framework == 'django':
        result = _run_command(['django-admin', 'startproject', project_name, project_path], timeout=30)
        if result.get('success'):
            return {'success': True, 'path': project_path, 'framework': 'django'}
        # Fallback: try with python -m django
        result = _run_command(['python3', '-m', 'django', 'startproject', project_name, project_path], timeout=30)
        if result.get('success'):
            return {'success': True, 'path': project_path, 'framework': 'django'}
        return {'error': 'Django not installed. Run: pip install django'}
    else:
        return {'error': f'Unknown Python framework: {framework}'}

    with open(os.path.join(project_path, 'main.py'), 'w') as f:
        f.write(main_py)
    with open(os.path.join(project_path, 'requirements.txt'), 'w') as f:
        f.write(requirements)

    return {'success': True, 'path': project_path, 'framework': framework}


def install_dependencies(project_path: str) -> dict[str, Any]:
    """Install project dependencies."""
    if os.path.exists(os.path.join(project_path, 'package.json')):
        return _run_command(['npm', 'install'], cwd=project_path, timeout=180)
    elif os.path.exists(os.path.join(project_path, 'requirements.txt')):
        return _run_command(['pip', 'install', '-r', 'requirements.txt'], cwd=project_path, timeout=120)
    return {'error': 'No package.json or requirements.txt found'}


def build(project_path: str) -> dict[str, Any]:
    """Build the project for production."""
    if os.path.exists(os.path.join(project_path, 'package.json')):
        return _run_command(['npm', 'run', 'build'], cwd=project_path, timeout=180)
    return {'message': 'No build step needed for this project type'}


def start_dev_server(project_path: str, port: int = 3000) -> dict[str, Any]:
    """Start the development server."""
    if os.path.exists(os.path.join(project_path, 'package.json')):
        return {'message': f'Run: cd {project_path} && npm run dev -- --port {port}'}
    elif os.path.exists(os.path.join(project_path, 'main.py')):
        return {'message': f'Run: cd {project_path} && uvicorn main:app --reload --port {port}'}
    return {'message': f'Run: cd {project_path} && python3 -m http.server {port}'}


def run_tests(project_path: str) -> dict[str, Any]:
    """Run the project test suite."""
    if os.path.exists(os.path.join(project_path, 'package.json')):
        return _run_command(['npm', 'test', '--', '--watchAll=false'], cwd=project_path, timeout=120)
    elif os.path.exists(os.path.join(project_path, 'pytest.ini')) or os.path.exists(os.path.join(project_path, 'tests')):
        return _run_command(['python3', '-m', 'pytest'], cwd=project_path, timeout=120)
    return {'message': 'No test configuration found'}


def deploy_vercel(project_path: str) -> dict[str, Any]:
    """Deploy to Vercel."""
    token = os.environ.get('VERCEL_TOKEN', '')
    cmd = ['npx', 'vercel', '--yes', '--prod']
    if token:
        cmd.extend(['--token', token])
    result = _run_command(cmd, cwd=project_path, timeout=300)
    if result.get('success'):
        return {'success': True, 'platform': 'vercel', 'output': result.get('stdout', '')}
    return result


def deploy_netlify(project_path: str) -> dict[str, Any]:
    """Deploy to Netlify."""
    token = os.environ.get('NETLIFY_TOKEN', '')
    cmd = ['npx', 'netlify-cli', 'deploy', '--prod', '--dir', '.']
    if token:
        cmd.extend(['--auth', token])
    result = _run_command(cmd, cwd=project_path, timeout=300)
    if result.get('success'):
        return {'success': True, 'platform': 'netlify', 'output': result.get('stdout', '')}
    return result


def execute_website_build_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a website build operation and return (content_string, result_data)."""
    try:
        project_path = params.get('project_path', '/workspace/web-app')

        if operation == 'create_project':
            result = create_project(
                params.get('project_name', 'my-web-app'),
                params.get('framework', 'nextjs'),
                project_path,
            )
        elif operation == 'install_dependencies':
            result = install_dependencies(project_path)
        elif operation == 'add_package':
            pkg = params.get('package_name', '')
            if os.path.exists(os.path.join(project_path, 'package.json')):
                result = _run_command(['npm', 'install', pkg], cwd=project_path, timeout=60)
            else:
                result = _run_command(['pip', 'install', pkg], cwd=project_path, timeout=60)
        elif operation == 'start_dev_server':
            result = start_dev_server(project_path, params.get('port', 3000))
        elif operation == 'build':
            result = build(project_path)
        elif operation == 'run_tests':
            result = run_tests(project_path)
        elif operation == 'deploy_vercel':
            result = deploy_vercel(project_path)
        elif operation == 'deploy_netlify':
            result = deploy_netlify(project_path)
        elif operation == 'deploy_github_pages':
            result = {'message': f'Run: cd {project_path} && npx gh-pages -d build'}
        elif operation in ('generate_page', 'generate_component', 'generate_api_route'):
            result = {'message': f'Use the file editor to create {params.get("component_name", "")} in {project_path}'}
        elif operation == 'add_database':
            db_type = params.get('database_type', 'sqlite')
            result = {'message': f'Set up {db_type} database. Use the file editor to add database configuration to {project_path}'}
        elif operation == 'add_auth':
            provider = params.get('auth_provider', 'jwt')
            result = {'message': f'Add {provider} authentication. Use the file editor to add auth configuration to {project_path}'}
        else:
            result = {'error': f'Unknown website build operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Website build operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
