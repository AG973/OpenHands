"""GitHub Operations tool for the CodeAct Agent.

Provides the agent with full GitHub access: search repos, read code, create PRs,
manage branches, clone repos, analyze/reverse engineer codebases.
Uses the GitHub REST API via requests (no extra dependencies needed).
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_GITHUB_DESCRIPTION = """Interact with GitHub to search repositories, read code, create pull requests, manage branches, and analyze codebases.

### Available Operations:
1. **search_repos** - Search GitHub for public repositories by keyword, language, stars, etc.
2. **search_code** - Search for code across all public GitHub repositories.
3. **get_repo_info** - Get detailed information about a specific repository (description, stars, language, etc.).
4. **list_repo_files** - List files and directories in a repository at a given path.
5. **read_file** - Read the contents of a specific file from a repository.
6. **get_repo_tree** - Get the full file tree of a repository (recursive directory listing).
7. **clone_repo** - Clone a repository to the local workspace for analysis or modification.
8. **create_branch** - Create a new branch in a repository.
9. **list_branches** - List all branches in a repository.
10. **create_pull_request** - Create a pull request in a repository.
11. **list_pull_requests** - List pull requests in a repository (open, closed, or all).
12. **get_commit_history** - Get recent commit history for a repository or specific file.
13. **fork_repo** - Fork a repository to the authenticated user's account.
14. **create_issue** - Create a new issue in a repository.
15. **list_issues** - List issues in a repository.
16. **analyze_repo** - Analyze a repository's architecture, dependencies, file structure, and patterns.

### Authentication:
- Set GITHUB_TOKEN environment variable for authenticated requests (higher rate limits, private repo access).
- Without a token, only public repos can be accessed with lower rate limits.

### Usage Notes:
- Use owner/repo format for repository references (e.g., "facebook/react").
- Search queries support GitHub's search qualifiers (e.g., "language:python stars:>1000").
- The analyze_repo operation provides architecture mapping, dependency detection, and code pattern analysis.
"""

GitHubTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='github',
        description=_GITHUB_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The GitHub operation to perform.',
                    'enum': [
                        'search_repos',
                        'search_code',
                        'get_repo_info',
                        'list_repo_files',
                        'read_file',
                        'get_repo_tree',
                        'clone_repo',
                        'create_branch',
                        'list_branches',
                        'create_pull_request',
                        'list_pull_requests',
                        'get_commit_history',
                        'fork_repo',
                        'create_issue',
                        'list_issues',
                        'analyze_repo',
                    ],
                },
                'repo': {
                    'type': 'string',
                    'description': 'Repository in owner/repo format (e.g., "facebook/react"). Required for most operations.',
                },
                'query': {
                    'type': 'string',
                    'description': 'Search query string. Used with search_repos and search_code operations. Supports GitHub search qualifiers.',
                },
                'path': {
                    'type': 'string',
                    'description': 'File or directory path within the repository. Used with list_repo_files, read_file operations. Defaults to root "/".',
                },
                'branch': {
                    'type': 'string',
                    'description': 'Branch name. Used with create_branch (new branch name), read_file, list_repo_files. Defaults to the default branch.',
                },
                'base_branch': {
                    'type': 'string',
                    'description': 'Base branch for create_branch or create_pull_request. Defaults to the default branch.',
                },
                'title': {
                    'type': 'string',
                    'description': 'Title for create_pull_request or create_issue.',
                },
                'body': {
                    'type': 'string',
                    'description': 'Body/description for create_pull_request or create_issue.',
                },
                'state': {
                    'type': 'string',
                    'description': 'Filter state for list_pull_requests or list_issues.',
                    'enum': ['open', 'closed', 'all'],
                },
                'clone_path': {
                    'type': 'string',
                    'description': 'Local path to clone the repository to. Used with clone_repo. Defaults to /workspace/<repo-name>.',
                },
            },
            'required': ['operation'],
        },
    ),
)
