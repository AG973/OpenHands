"""GitHub operations execution handler.

Executes GitHub API calls using the requests library (no extra dependencies).
Uses the GitHub REST API v3.
"""

import json
import os
import subprocess
from typing import Any

import requests

from openhands.core.logger import openhands_logger as logger

GITHUB_API_BASE = 'https://api.github.com'


def _get_headers() -> dict[str, str]:
    """Get GitHub API headers with optional authentication."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'OpenHands-Agent',
    }
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        headers['Authorization'] = f'token {token}'
    return headers


def _api_get(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the GitHub API."""
    url = f'{GITHUB_API_BASE}{endpoint}'
    try:
        resp = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {'error': str(e), 'status_code': resp.status_code, 'message': resp.text}
    except Exception as e:
        return {'error': str(e)}


def _api_post(endpoint: str, data: dict | None = None) -> dict[str, Any]:
    """Make a POST request to the GitHub API."""
    url = f'{GITHUB_API_BASE}{endpoint}'
    try:
        resp = requests.post(url, headers=_get_headers(), json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {'error': str(e), 'status_code': resp.status_code, 'message': resp.text}
    except Exception as e:
        return {'error': str(e)}


def search_repos(query: str) -> dict[str, Any]:
    """Search GitHub for repositories."""
    return _api_get('/search/repositories', params={'q': query, 'per_page': 20, 'sort': 'stars'})


def search_code(query: str) -> dict[str, Any]:
    """Search GitHub for code."""
    return _api_get('/search/code', params={'q': query, 'per_page': 20})


def get_repo_info(repo: str) -> dict[str, Any]:
    """Get detailed info about a repository."""
    return _api_get(f'/repos/{repo}')


def list_repo_files(repo: str, path: str = '', branch: str = '') -> dict[str, Any]:
    """List files in a repository directory."""
    params = {}
    if branch:
        params['ref'] = branch
    endpoint = f'/repos/{repo}/contents/{path}'
    return _api_get(endpoint, params=params)


def read_file(repo: str, path: str, branch: str = '') -> dict[str, Any]:
    """Read the contents of a file from a repository."""
    params = {}
    if branch:
        params['ref'] = branch
    result = _api_get(f'/repos/{repo}/contents/{path}', params=params)
    if isinstance(result, dict) and 'content' in result:
        import base64
        try:
            decoded = base64.b64decode(result['content']).decode('utf-8')
            result['decoded_content'] = decoded
        except Exception:
            result['decoded_content'] = '[Binary file - cannot decode]'
    return result


def get_repo_tree(repo: str, branch: str = '') -> dict[str, Any]:
    """Get the full file tree of a repository."""
    if not branch:
        repo_info = get_repo_info(repo)
        if 'error' in repo_info:
            return repo_info
        branch = repo_info.get('default_branch', 'main')
    return _api_get(f'/repos/{repo}/git/trees/{branch}', params={'recursive': '1'})


def clone_repo(repo: str, clone_path: str = '') -> dict[str, Any]:
    """Clone a repository to the local workspace."""
    if not clone_path:
        repo_name = repo.split('/')[-1]
        clone_path = f'/workspace/{repo_name}'

    clone_url = f'https://github.com/{repo}.git'
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        clone_url = f'https://{token}@github.com/{repo}.git'

    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', clone_url, clone_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {'success': True, 'path': clone_path, 'message': f'Cloned {repo} to {clone_path}'}
        else:
            return {'error': result.stderr, 'returncode': result.returncode}
    except subprocess.TimeoutExpired:
        return {'error': 'Clone timed out after 120 seconds'}
    except Exception as e:
        return {'error': str(e)}


def create_branch(repo: str, branch: str, base_branch: str = '') -> dict[str, Any]:
    """Create a new branch in a repository."""
    if not base_branch:
        repo_info = get_repo_info(repo)
        if 'error' in repo_info:
            return repo_info
        base_branch = repo_info.get('default_branch', 'main')

    # Get the SHA of the base branch
    ref_data = _api_get(f'/repos/{repo}/git/refs/heads/{base_branch}')
    if 'error' in ref_data:
        return ref_data
    sha = ref_data.get('object', {}).get('sha', '')
    if not sha:
        return {'error': f'Could not get SHA for branch {base_branch}'}

    return _api_post(f'/repos/{repo}/git/refs', data={
        'ref': f'refs/heads/{branch}',
        'sha': sha,
    })


def list_branches(repo: str) -> dict[str, Any]:
    """List all branches in a repository."""
    return _api_get(f'/repos/{repo}/branches', params={'per_page': 100})


def create_pull_request(repo: str, title: str, body: str = '', branch: str = '', base_branch: str = '') -> dict[str, Any]:
    """Create a pull request in a repository."""
    if not base_branch:
        repo_info = get_repo_info(repo)
        if 'error' in repo_info:
            return repo_info
        base_branch = repo_info.get('default_branch', 'main')

    data = {
        'title': title,
        'body': body or '',
        'head': branch,
        'base': base_branch,
    }
    return _api_post(f'/repos/{repo}/pulls', data=data)


def list_pull_requests(repo: str, state: str = 'open') -> dict[str, Any]:
    """List pull requests in a repository."""
    return _api_get(f'/repos/{repo}/pulls', params={'state': state, 'per_page': 30})


def get_commit_history(repo: str, path: str = '', branch: str = '') -> dict[str, Any]:
    """Get recent commit history."""
    params: dict[str, str] = {'per_page': '20'}
    if path:
        params['path'] = path
    if branch:
        params['sha'] = branch
    return _api_get(f'/repos/{repo}/commits', params=params)


def fork_repo(repo: str) -> dict[str, Any]:
    """Fork a repository to the authenticated user's account."""
    return _api_post(f'/repos/{repo}/forks')


def create_issue(repo: str, title: str, body: str = '') -> dict[str, Any]:
    """Create a new issue in a repository."""
    return _api_post(f'/repos/{repo}/issues', data={'title': title, 'body': body or ''})


def list_issues(repo: str, state: str = 'open') -> dict[str, Any]:
    """List issues in a repository."""
    return _api_get(f'/repos/{repo}/issues', params={'state': state, 'per_page': 30})


def analyze_repo(repo: str) -> dict[str, Any]:
    """Analyze a repository's architecture, dependencies, and patterns."""
    analysis: dict[str, Any] = {'repo': repo, 'analysis': {}}

    # Get repo info
    info = get_repo_info(repo)
    if 'error' in info:
        return info
    analysis['analysis']['overview'] = {
        'name': info.get('name', ''),
        'description': info.get('description', ''),
        'language': info.get('language', ''),
        'stars': info.get('stargazers_count', 0),
        'forks': info.get('forks_count', 0),
        'size_kb': info.get('size', 0),
        'default_branch': info.get('default_branch', 'main'),
        'topics': info.get('topics', []),
        'license': info.get('license', {}).get('spdx_id', 'Unknown') if info.get('license') else 'None',
        'created_at': info.get('created_at', ''),
        'updated_at': info.get('updated_at', ''),
    }

    # Get languages breakdown
    languages = _api_get(f'/repos/{repo}/languages')
    if not isinstance(languages, dict) or 'error' not in languages:
        analysis['analysis']['languages'] = languages

    # Get file tree to understand structure
    tree = get_repo_tree(repo)
    if isinstance(tree, dict) and 'tree' in tree:
        tree_items = tree['tree']
        # Count file types
        file_types: dict[str, int] = {}
        directories: list[str] = []
        total_files = 0
        for item in tree_items:
            if item.get('type') == 'blob':
                total_files += 1
                ext = item['path'].rsplit('.', 1)[-1] if '.' in item['path'] else 'no-ext'
                file_types[ext] = file_types.get(ext, 0) + 1
            elif item.get('type') == 'tree':
                directories.append(item['path'])

        analysis['analysis']['structure'] = {
            'total_files': total_files,
            'total_directories': len(directories),
            'file_types': dict(sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:20]),
            'top_level_dirs': [d for d in directories if '/' not in d],
        }

    # Check for common config files to detect patterns
    config_files_to_check = [
        'package.json', 'requirements.txt', 'setup.py', 'pyproject.toml',
        'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
        'Dockerfile', 'docker-compose.yml', '.github/workflows',
        'Makefile', 'tsconfig.json', '.eslintrc.json', '.prettierrc',
    ]
    detected_configs = []
    for cf in config_files_to_check:
        result = _api_get(f'/repos/{repo}/contents/{cf}')
        if isinstance(result, (dict, list)) and 'error' not in (result if isinstance(result, dict) else {}):
            detected_configs.append(cf)

    analysis['analysis']['detected_configs'] = detected_configs

    # Detect patterns based on configs
    patterns = []
    if 'package.json' in detected_configs:
        patterns.append('Node.js/JavaScript project')
    if 'requirements.txt' in detected_configs or 'pyproject.toml' in detected_configs or 'setup.py' in detected_configs:
        patterns.append('Python project')
    if 'Cargo.toml' in detected_configs:
        patterns.append('Rust project')
    if 'go.mod' in detected_configs:
        patterns.append('Go project')
    if 'Dockerfile' in detected_configs or 'docker-compose.yml' in detected_configs:
        patterns.append('Docker containerized')
    if '.github/workflows' in detected_configs:
        patterns.append('GitHub Actions CI/CD')
    if 'tsconfig.json' in detected_configs:
        patterns.append('TypeScript')

    analysis['analysis']['patterns'] = patterns

    # Get contributors
    contributors = _api_get(f'/repos/{repo}/contributors', params={'per_page': '10'})
    if isinstance(contributors, list):
        analysis['analysis']['top_contributors'] = [
            {'login': c.get('login', ''), 'contributions': c.get('contributions', 0)}
            for c in contributors[:10]
        ]

    return analysis


def execute_github_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a GitHub operation and return (content_string, result_data)."""
    try:
        if operation == 'search_repos':
            result = search_repos(params.get('query', ''))
        elif operation == 'search_code':
            result = search_code(params.get('query', ''))
        elif operation == 'get_repo_info':
            result = get_repo_info(params.get('repo', ''))
        elif operation == 'list_repo_files':
            result = list_repo_files(params.get('repo', ''), params.get('path', ''), params.get('branch', ''))
        elif operation == 'read_file':
            result = read_file(params.get('repo', ''), params.get('path', ''), params.get('branch', ''))
        elif operation == 'get_repo_tree':
            result = get_repo_tree(params.get('repo', ''), params.get('branch', ''))
        elif operation == 'clone_repo':
            result = clone_repo(params.get('repo', ''), params.get('clone_path', ''))
        elif operation == 'create_branch':
            result = create_branch(params.get('repo', ''), params.get('branch', ''), params.get('base_branch', ''))
        elif operation == 'list_branches':
            result = list_branches(params.get('repo', ''))
        elif operation == 'create_pull_request':
            result = create_pull_request(
                params.get('repo', ''), params.get('title', ''),
                params.get('body', ''), params.get('branch', ''),
                params.get('base_branch', '')
            )
        elif operation == 'list_pull_requests':
            result = list_pull_requests(params.get('repo', ''), params.get('state', 'open'))
        elif operation == 'get_commit_history':
            result = get_commit_history(params.get('repo', ''), params.get('path', ''), params.get('branch', ''))
        elif operation == 'fork_repo':
            result = fork_repo(params.get('repo', ''))
        elif operation == 'create_issue':
            result = create_issue(params.get('repo', ''), params.get('title', ''), params.get('body', ''))
        elif operation == 'list_issues':
            result = list_issues(params.get('repo', ''), params.get('state', 'open'))
        elif operation == 'analyze_repo':
            result = analyze_repo(params.get('repo', ''))
        else:
            result = {'error': f'Unknown GitHub operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'GitHub operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
