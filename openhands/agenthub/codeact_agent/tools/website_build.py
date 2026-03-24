"""Website Building tool for the CodeAct Agent.

Provides the agent with capabilities to create, build, and deploy
websites and web applications using modern frameworks.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_WEBSITE_BUILD_DESCRIPTION = """Create, build, and deploy websites and web applications using modern frameworks.

### Available Operations:

**Project Setup:**
1. **create_project** - Create a new web project from a framework template.
2. **install_dependencies** - Install project dependencies.
3. **add_package** - Add a package to the web project.

**Development:**
4. **start_dev_server** - Start the development server with hot reload.
5. **generate_page** - Generate a new page/route with boilerplate code.
6. **generate_component** - Generate a reusable UI component.
7. **generate_api_route** - Generate an API endpoint/route.
8. **add_database** - Set up a database connection (SQLite, PostgreSQL, MySQL, MongoDB).
9. **add_auth** - Add authentication (email/password, OAuth, social login).

**Building:**
10. **build** - Build the project for production.
11. **build_static** - Generate a static site export.
12. **build_docker** - Generate a Dockerfile and build a Docker image.

**Testing:**
13. **run_tests** - Run the project test suite.
14. **lighthouse_audit** - Run a Lighthouse performance audit on the site.
15. **check_accessibility** - Check accessibility compliance (WCAG).

**Deployment:**
16. **deploy_vercel** - Deploy to Vercel.
17. **deploy_netlify** - Deploy to Netlify.
18. **deploy_cloudflare** - Deploy to Cloudflare Pages.
19. **deploy_github_pages** - Deploy to GitHub Pages.
20. **deploy_custom** - Deploy to a custom server via SSH/SFTP.

### Frameworks:
- **nextjs** - Next.js (React, SSR/SSG/ISR)
- **react** - Create React App / Vite React
- **vue** - Vue.js with Vite
- **svelte** - SvelteKit
- **astro** - Astro (static site builder)
- **html** - Plain HTML/CSS/JS
- **express** - Express.js backend
- **fastapi** - Python FastAPI backend
- **django** - Python Django full-stack
- **flask** - Python Flask backend

### Usage Notes:
- Use create_project to scaffold a new project with the chosen framework.
- The dev server supports hot module replacement for instant feedback.
- Set VERCEL_TOKEN, NETLIFY_TOKEN, or CLOUDFLARE_TOKEN for deployment.
- Database setup includes migrations and model generation.
"""

WebsiteBuildTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='website_build',
        description=_WEBSITE_BUILD_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The website build operation to perform.',
                    'enum': [
                        'create_project',
                        'install_dependencies',
                        'add_package',
                        'start_dev_server',
                        'generate_page',
                        'generate_component',
                        'generate_api_route',
                        'add_database',
                        'add_auth',
                        'build',
                        'build_static',
                        'build_docker',
                        'run_tests',
                        'lighthouse_audit',
                        'check_accessibility',
                        'deploy_vercel',
                        'deploy_netlify',
                        'deploy_cloudflare',
                        'deploy_github_pages',
                        'deploy_custom',
                    ],
                },
                'project_name': {
                    'type': 'string',
                    'description': 'Name of the web project to create.',
                },
                'project_path': {
                    'type': 'string',
                    'description': 'Path to the web project directory.',
                },
                'framework': {
                    'type': 'string',
                    'description': 'Web framework to use.',
                    'enum': [
                        'nextjs', 'react', 'vue', 'svelte', 'astro',
                        'html', 'express', 'fastapi', 'django', 'flask',
                    ],
                },
                'page_name': {
                    'type': 'string',
                    'description': 'Name of the page or route to generate.',
                },
                'component_name': {
                    'type': 'string',
                    'description': 'Name of the component to generate.',
                },
                'component_description': {
                    'type': 'string',
                    'description': 'Description of the component or page functionality.',
                },
                'api_route': {
                    'type': 'string',
                    'description': 'API route path (e.g., "/api/users").',
                },
                'api_method': {
                    'type': 'string',
                    'description': 'HTTP method for the API route.',
                    'enum': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
                },
                'database_type': {
                    'type': 'string',
                    'description': 'Type of database to set up.',
                    'enum': ['sqlite', 'postgresql', 'mysql', 'mongodb'],
                },
                'auth_provider': {
                    'type': 'string',
                    'description': 'Authentication provider to add.',
                    'enum': ['email', 'google', 'github', 'facebook', 'apple', 'jwt'],
                },
                'package_name': {
                    'type': 'string',
                    'description': 'NPM/pip package name to add.',
                },
                'deploy_url': {
                    'type': 'string',
                    'description': 'Custom deployment URL or server address.',
                },
                'port': {
                    'type': 'number',
                    'description': 'Port number for the dev server. Default: 3000.',
                },
            },
            'required': ['operation'],
        },
    ),
)
