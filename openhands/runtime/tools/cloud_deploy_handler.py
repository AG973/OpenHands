"""Cloud deployment operations execution handler.

Executes cloud deployment operations using CLI tools and REST APIs.
Supports AWS, GCP, Azure, RunPod, and Docker.
"""

import json
import os
import subprocess
from typing import Any

from openhands.core.logger import openhands_logger as logger


def _run_command(cmd: list[str], timeout: int = 120, cwd: str | None = None) -> dict[str, Any]:
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


def aws_deploy_s3(project_path: str, service_name: str, region: str = 'us-east-1') -> dict[str, Any]:
    """Deploy static files to S3."""
    if not _check_cli('aws'):
        return {'error': 'AWS CLI not installed. Run: pip install awscli'}
    bucket = service_name
    cmds = [
        ['aws', 's3', 'mb', f's3://{bucket}', '--region', region],
        ['aws', 's3', 'sync', project_path, f's3://{bucket}', '--acl', 'public-read'],
        ['aws', 's3', 'website', f's3://{bucket}', '--index-document', 'index.html', '--error-document', 'error.html'],
    ]
    results = []
    for cmd in cmds:
        r = _run_command(cmd)
        results.append(r)
        if not r.get('success'):
            return {'error': f'Failed at step: {" ".join(cmd)}', 'details': r}
    return {
        'success': True,
        'url': f'http://{bucket}.s3-website-{region}.amazonaws.com',
        'bucket': bucket,
        'message': f'Deployed to S3 bucket {bucket}',
    }


def aws_deploy_lambda(project_path: str, service_name: str, region: str = 'us-east-1') -> dict[str, Any]:
    """Deploy a function to AWS Lambda."""
    if not _check_cli('aws'):
        return {'error': 'AWS CLI not installed. Run: pip install awscli'}
    # Create zip of project
    zip_path = f'/tmp/{service_name}.zip'
    _run_command(['zip', '-r', zip_path, '.'], timeout=60, cwd=project_path)
    result = _run_command([
        'aws', 'lambda', 'create-function',
        '--function-name', service_name,
        '--runtime', 'python3.11',
        '--handler', 'handler.handler',
        '--zip-file', f'fileb://{zip_path}',
        '--region', region,
    ])
    if result.get('success'):
        return {'success': True, 'function_name': service_name, 'message': f'Lambda function {service_name} deployed'}
    return result


def docker_build(project_path: str, docker_image: str, dockerfile_path: str = 'Dockerfile') -> dict[str, Any]:
    """Build a Docker image."""
    if not _check_cli('docker'):
        return {'error': 'Docker not installed or not running.'}
    result = _run_command(['docker', 'build', '-t', docker_image, '-f', dockerfile_path, project_path], timeout=300)
    if result.get('success'):
        return {'success': True, 'image': docker_image, 'message': f'Built Docker image {docker_image}'}
    return result


def docker_push(docker_image: str) -> dict[str, Any]:
    """Push a Docker image to a registry."""
    if not _check_cli('docker'):
        return {'error': 'Docker not installed or not running.'}
    result = _run_command(['docker', 'push', docker_image], timeout=300)
    if result.get('success'):
        return {'success': True, 'image': docker_image, 'message': f'Pushed Docker image {docker_image}'}
    return result


def runpod_deploy_pod(gpu_type: str = 'NVIDIA RTX A6000', gpu_count: int = 1,
                      docker_image: str = 'runpod/pytorch:latest', disk_size: int = 20) -> dict[str, Any]:
    """Deploy a GPU pod on RunPod."""
    import requests
    api_key = os.environ.get('RUNPOD_API_KEY', '')
    if not api_key:
        return {'error': 'RUNPOD_API_KEY environment variable not set.'}

    query = '''
    mutation($input: PodFindAndDeployOnDemandInput!) {
        podFindAndDeployOnDemand(input: $input) {
            id
            name
            gpuCount
            machineId
            runtime { ports { ip port } }
        }
    }
    '''
    variables = {
        'input': {
            'name': 'openhands-pod',
            'imageName': docker_image,
            'gpuTypeId': gpu_type,
            'gpuCount': gpu_count,
            'volumeInGb': disk_size,
            'containerDiskInGb': 20,
            'minVcpuCount': 2,
            'minMemoryInGb': 8,
        }
    }

    try:
        resp = requests.post(
            'https://api.runpod.io/graphql',
            json={'query': query, 'variables': variables},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=60,
        )
        data = resp.json()
        return {'success': True, 'data': data}
    except Exception as e:
        return {'error': str(e)}


def runpod_list_pods() -> dict[str, Any]:
    """List running RunPod instances."""
    import requests
    api_key = os.environ.get('RUNPOD_API_KEY', '')
    if not api_key:
        return {'error': 'RUNPOD_API_KEY environment variable not set.'}

    query = '{ myself { pods { id name gpuCount runtime { ports { ip port } } } } }'
    try:
        resp = requests.post(
            'https://api.runpod.io/graphql',
            json={'query': query},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def gcp_deploy_cloud_run(project_path: str, service_name: str, region: str = 'us-central1') -> dict[str, Any]:
    """Deploy to Google Cloud Run."""
    if not _check_cli('gcloud'):
        return {'error': 'gcloud CLI not installed. Visit: https://cloud.google.com/sdk/docs/install'}
    result = _run_command([
        'gcloud', 'run', 'deploy', service_name,
        '--source', project_path,
        '--region', region,
        '--allow-unauthenticated',
    ], timeout=300)
    if result.get('success'):
        return {'success': True, 'service': service_name, 'region': region}
    return result


def azure_deploy_app_service(project_path: str, service_name: str, region: str = 'eastus') -> dict[str, Any]:
    """Deploy to Azure App Service."""
    if not _check_cli('az'):
        return {'error': 'Azure CLI not installed. Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli'}
    result = _run_command([
        'az', 'webapp', 'up',
        '--name', service_name,
        '--location', region,
        '--sku', 'F1',
    ], timeout=300)
    if result.get('success'):
        return {'success': True, 'url': f'https://{service_name}.azurewebsites.net'}
    return result


def execute_cloud_deploy_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a cloud deployment operation and return (content_string, result_data)."""
    try:
        project_path = params.get('project_path', '.')
        service_name = params.get('service_name', 'openhands-app')
        region = params.get('region', 'us-east-1')

        if operation == 'aws_deploy_s3':
            result = aws_deploy_s3(project_path, service_name, region)
        elif operation == 'aws_deploy_lambda':
            result = aws_deploy_lambda(project_path, service_name, region)
        elif operation == 'aws_configure':
            result = {'message': 'Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, then run: aws configure'}
        elif operation == 'gcp_deploy_cloud_run':
            result = gcp_deploy_cloud_run(project_path, service_name, region)
        elif operation == 'gcp_configure':
            result = {'message': 'Set GOOGLE_APPLICATION_CREDENTIALS environment variable or run: gcloud auth login'}
        elif operation == 'azure_deploy_app_service':
            result = azure_deploy_app_service(project_path, service_name, region)
        elif operation == 'azure_configure':
            result = {'message': 'Run: az login'}
        elif operation == 'runpod_deploy_pod':
            result = runpod_deploy_pod(
                params.get('gpu_type', 'NVIDIA RTX A6000'),
                params.get('gpu_count', 1),
                params.get('docker_image', 'runpod/pytorch:latest'),
                params.get('disk_size', 20),
            )
        elif operation == 'runpod_list_pods':
            result = runpod_list_pods()
        elif operation == 'runpod_configure':
            result = {'message': 'Set RUNPOD_API_KEY environment variable. Get your key at: https://www.runpod.io/console/user/settings'}
        elif operation == 'docker_build':
            result = docker_build(project_path, params.get('docker_image', 'app:latest'), params.get('dockerfile_path', 'Dockerfile'))
        elif operation == 'docker_push':
            result = docker_push(params.get('docker_image', ''))
        elif operation == 'deploy_status':
            result = {'message': 'Check deployment status using platform-specific commands (aws, gcloud, az, runpod)'}
        elif operation == 'list_deployments':
            result = {'message': 'Use platform-specific list commands to see active deployments'}
        else:
            result = {'error': f'Unknown cloud deploy operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Cloud deploy operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
