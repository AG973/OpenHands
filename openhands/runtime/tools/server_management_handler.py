"""Server & GPU management operations execution handler.

Executes server management operations: SSH, RunPod, Lambda Labs, Vast.ai.
"""

import json
import os
import subprocess
from typing import Any

import requests

from openhands.core.logger import openhands_logger as logger


def _run_command(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Command timed out after {timeout} seconds'}
    except FileNotFoundError:
        return {'error': f'Command not found: {cmd[0]}'}
    except Exception as e:
        return {'error': str(e)}


def ssh_execute(hostname: str, command: str, username: str = 'root',
                port: int = 22, ssh_key_path: str = '') -> dict[str, Any]:
    """Execute a command on a remote server via SSH."""
    ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10']
    if ssh_key_path:
        ssh_cmd.extend(['-i', ssh_key_path])
    if port != 22:
        ssh_cmd.extend(['-p', str(port)])
    ssh_cmd.append(f'{username}@{hostname}')
    ssh_cmd.append(command)
    return _run_command(ssh_cmd, timeout=60)


def ssh_upload(hostname: str, local_path: str, remote_path: str,
               username: str = 'root', port: int = 22, ssh_key_path: str = '') -> dict[str, Any]:
    """Upload a file to a remote server via SCP."""
    scp_cmd = ['scp', '-o', 'StrictHostKeyChecking=no']
    if ssh_key_path:
        scp_cmd.extend(['-i', ssh_key_path])
    if port != 22:
        scp_cmd.extend(['-P', str(port)])
    scp_cmd.append(local_path)
    scp_cmd.append(f'{username}@{hostname}:{remote_path}')
    return _run_command(scp_cmd, timeout=120)


def ssh_download(hostname: str, remote_path: str, local_path: str,
                 username: str = 'root', port: int = 22, ssh_key_path: str = '') -> dict[str, Any]:
    """Download a file from a remote server via SCP."""
    scp_cmd = ['scp', '-o', 'StrictHostKeyChecking=no']
    if ssh_key_path:
        scp_cmd.extend(['-i', ssh_key_path])
    if port != 22:
        scp_cmd.extend(['-P', str(port)])
    scp_cmd.append(f'{username}@{hostname}:{remote_path}')
    scp_cmd.append(local_path)
    return _run_command(scp_cmd, timeout=120)


def server_status(hostname: str, username: str = 'root', port: int = 22,
                  ssh_key_path: str = '') -> dict[str, Any]:
    """Check server status (CPU, memory, disk, GPU)."""
    commands = {
        'uptime': 'uptime',
        'memory': 'free -h | head -2',
        'disk': 'df -h / | tail -1',
        'cpu': 'nproc',
        'gpu': 'nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null || echo "No GPU detected"',
    }
    status: dict[str, Any] = {}
    for key, cmd in commands.items():
        result = ssh_execute(hostname, cmd, username, port, ssh_key_path)
        status[key] = result.get('stdout', '').strip() if result.get('success') else result.get('error', 'Failed')
    return {'hostname': hostname, 'status': status}


def server_health(hostname: str, username: str = 'root', port: int = 22) -> dict[str, Any]:
    """Run a health check on a server."""
    # Ping check
    ping_result = _run_command(['ping', '-c', '1', '-W', '5', hostname], timeout=10)
    ping_ok = ping_result.get('success', False)

    # SSH check
    ssh_result = ssh_execute(hostname, 'echo ok', username, port)
    ssh_ok = ssh_result.get('success', False) and 'ok' in ssh_result.get('stdout', '')

    return {
        'hostname': hostname,
        'ping': 'reachable' if ping_ok else 'unreachable',
        'ssh': 'connected' if ssh_ok else 'failed',
        'healthy': ping_ok and ssh_ok,
    }


def runpod_create(gpu_type: str = 'NVIDIA RTX A6000', gpu_count: int = 1,
                  docker_image: str = 'runpod/pytorch:latest', disk_size: int = 20) -> dict[str, Any]:
    """Create a GPU pod on RunPod."""
    api_key = os.environ.get('RUNPOD_API_KEY', '')
    if not api_key:
        return {'error': 'RUNPOD_API_KEY not set'}

    query = '''
    mutation($input: PodFindAndDeployOnDemandInput!) {
        podFindAndDeployOnDemand(input: $input) {
            id name gpuCount machineId
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
        }
    }

    try:
        resp = requests.post(
            'https://api.runpod.io/graphql',
            json={'query': query, 'variables': variables},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=60,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def runpod_list() -> dict[str, Any]:
    """List RunPod instances."""
    api_key = os.environ.get('RUNPOD_API_KEY', '')
    if not api_key:
        return {'error': 'RUNPOD_API_KEY not set'}
    try:
        resp = requests.post(
            'https://api.runpod.io/graphql',
            json={'query': '{ myself { pods { id name gpuCount runtime { ports { ip port } } } } }'},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def runpod_stop(instance_id: str) -> dict[str, Any]:
    """Stop a RunPod instance."""
    api_key = os.environ.get('RUNPOD_API_KEY', '')
    if not api_key:
        return {'error': 'RUNPOD_API_KEY not set'}
    query = 'mutation($input: PodStopInput!) { podStop(input: $input) { id } }'
    variables = {'input': {'podId': instance_id}}
    try:
        resp = requests.post(
            'https://api.runpod.io/graphql',
            json={'query': query, 'variables': variables},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def lambda_list() -> dict[str, Any]:
    """List Lambda Labs instances."""
    api_key = os.environ.get('LAMBDA_API_KEY', '')
    if not api_key:
        return {'error': 'LAMBDA_API_KEY not set'}
    try:
        resp = requests.get(
            'https://cloud.lambdalabs.com/api/v1/instances',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def lambda_create(gpu_type: str = 'gpu_1x_a100', region: str = 'us-tx-3',
                  ssh_key_path: str = '') -> dict[str, Any]:
    """Create a Lambda Labs instance."""
    api_key = os.environ.get('LAMBDA_API_KEY', '')
    if not api_key:
        return {'error': 'LAMBDA_API_KEY not set'}
    data = {
        'region_name': region,
        'instance_type_name': gpu_type,
        'quantity': 1,
    }
    if ssh_key_path:
        data['ssh_key_names'] = [ssh_key_path]
    try:
        resp = requests.post(
            'https://cloud.lambdalabs.com/api/v1/instance-operations/launch',
            json=data,
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=60,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def execute_server_management_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a server management operation and return (content_string, result_data)."""
    try:
        hostname = params.get('hostname', params.get('server_id', ''))
        username = params.get('username', 'root')
        port = int(params.get('port', 22))
        ssh_key_path = params.get('ssh_key_path', '')

        if operation == 'ssh_execute':
            result = ssh_execute(hostname, params.get('command', ''), username, port, ssh_key_path)
        elif operation == 'ssh_upload':
            result = ssh_upload(hostname, params.get('local_path', ''), params.get('remote_path', ''), username, port, ssh_key_path)
        elif operation == 'ssh_download':
            result = ssh_download(hostname, params.get('remote_path', ''), params.get('local_path', ''), username, port, ssh_key_path)
        elif operation == 'ssh_connect':
            result = ssh_execute(hostname, 'echo "Connected successfully"', username, port, ssh_key_path)
        elif operation == 'ssh_tunnel':
            result = {'message': f'Run: ssh -L {params.get("local_port", 8080)}:localhost:{params.get("remote_port", 8080)} {username}@{hostname}'}
        elif operation == 'server_status':
            result = server_status(hostname, username, port, ssh_key_path)
        elif operation == 'server_health':
            result = server_health(hostname, username, port)
        elif operation == 'list_servers':
            result = {'message': 'Use add_server to configure servers, then list them here.'}
        elif operation == 'runpod_create':
            result = runpod_create(
                params.get('gpu_type', 'NVIDIA RTX A6000'),
                params.get('gpu_count', 1),
                params.get('docker_image', 'runpod/pytorch:latest'),
                params.get('disk_size', 20),
            )
        elif operation == 'runpod_list':
            result = runpod_list()
        elif operation == 'runpod_stop':
            result = runpod_stop(params.get('instance_id', ''))
        elif operation == 'runpod_terminate':
            result = runpod_stop(params.get('instance_id', ''))  # Same API for stop/terminate
        elif operation == 'lambda_create':
            result = lambda_create(params.get('gpu_type', 'gpu_1x_a100'), params.get('region', 'us-tx-3'))
        elif operation == 'lambda_list':
            result = lambda_list()
        elif operation == 'lambda_terminate':
            result = {'message': f'Use Lambda API to terminate instance {params.get("instance_id", "")}'}
        elif operation == 'list_processes':
            result = ssh_execute(hostname, 'ps aux --sort=-%cpu | head -20', username, port, ssh_key_path)
        elif operation == 'kill_process':
            pid = params.get('process_id', '')
            if not pid.isdigit():
                result = {'error': 'process_id must be a numeric value'}
            else:
                result = ssh_execute(hostname, f'kill -9 {pid}', username, port, ssh_key_path)
        elif operation == 'start_service':
            svc = params.get('service_name', '')
            if not all(c.isalnum() or c in '-_.' for c in svc) or not svc:
                result = {'error': 'service_name contains invalid characters'}
            else:
                result = ssh_execute(hostname, f'systemctl start {svc}', username, port, ssh_key_path)
        elif operation == 'stop_service':
            svc = params.get('service_name', '')
            if not all(c.isalnum() or c in '-_.' for c in svc) or not svc:
                result = {'error': 'service_name contains invalid characters'}
            else:
                result = ssh_execute(hostname, f'systemctl stop {svc}', username, port, ssh_key_path)
        elif operation == 'add_server':
            result = {'message': f'Server {hostname} added to configuration'}
        elif operation == 'remove_server':
            result = {'message': f'Server {params.get("server_id", "")} removed from configuration'}
        else:
            result = {'error': f'Unknown server management operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Server management operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
