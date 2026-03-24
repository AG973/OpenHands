"""Server & GPU Management tool for the CodeAct Agent.

Provides the agent with capabilities to connect to and manage local servers,
cloud GPU servers (RunPod, Lambda Labs, Vast.ai), and remote machines via SSH.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_SERVER_MANAGEMENT_DESCRIPTION = """Connect to and manage local servers, cloud GPU instances, and remote machines.

### Available Operations:

**SSH Operations:**
1. **ssh_connect** - Establish an SSH connection to a remote server.
2. **ssh_execute** - Execute a command on a remote server via SSH.
3. **ssh_upload** - Upload a file to a remote server via SCP/SFTP.
4. **ssh_download** - Download a file from a remote server via SCP/SFTP.
5. **ssh_tunnel** - Create an SSH tunnel for port forwarding.

**Server Discovery & Status:**
6. **list_servers** - List all configured/connected servers.
7. **server_status** - Check the status of a server (CPU, memory, disk, GPU utilization).
8. **server_health** - Run a health check on a server (ping, SSH, services).

**GPU Server Management:**
9. **runpod_create** - Create a new GPU pod on RunPod.
10. **runpod_list** - List running RunPod instances.
11. **runpod_stop** - Stop a RunPod instance.
12. **runpod_terminate** - Terminate and delete a RunPod instance.
13. **lambda_create** - Create a new instance on Lambda Labs.
14. **lambda_list** - List Lambda Labs instances.
15. **lambda_terminate** - Terminate a Lambda Labs instance.
16. **vastai_create** - Create a new instance on Vast.ai.
17. **vastai_list** - List Vast.ai instances.
18. **vastai_terminate** - Terminate a Vast.ai instance.

**Process Management:**
19. **list_processes** - List running processes on a server.
20. **kill_process** - Kill a process on a server.
21. **start_service** - Start a service on a server (systemctl/pm2).
22. **stop_service** - Stop a service on a server.

**Server Configuration:**
23. **add_server** - Add a new server to the configuration (hostname, SSH key, etc.).
24. **remove_server** - Remove a server from the configuration.
25. **configure_firewall** - Configure firewall rules on a server.

### Authentication:
- SSH: Use SSH keys (set SSH_PRIVATE_KEY_PATH) or password authentication.
- RunPod: Set RUNPOD_API_KEY environment variable.
- Lambda Labs: Set LAMBDA_API_KEY environment variable.
- Vast.ai: Set VASTAI_API_KEY environment variable.

### Usage Notes:
- SSH connections persist during the session for efficiency.
- GPU server creation includes automatic SSH key setup for immediate access.
- Server status includes GPU utilization when NVIDIA GPUs are detected.
- Port forwarding via SSH tunnel enables accessing remote services locally.
"""

ServerManagementTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='server_management',
        description=_SERVER_MANAGEMENT_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The server management operation to perform.',
                    'enum': [
                        'ssh_connect',
                        'ssh_execute',
                        'ssh_upload',
                        'ssh_download',
                        'ssh_tunnel',
                        'list_servers',
                        'server_status',
                        'server_health',
                        'runpod_create',
                        'runpod_list',
                        'runpod_stop',
                        'runpod_terminate',
                        'lambda_create',
                        'lambda_list',
                        'lambda_terminate',
                        'vastai_create',
                        'vastai_list',
                        'vastai_terminate',
                        'list_processes',
                        'kill_process',
                        'start_service',
                        'stop_service',
                        'add_server',
                        'remove_server',
                        'configure_firewall',
                    ],
                },
                'server_id': {
                    'type': 'string',
                    'description': 'Server identifier (hostname, IP address, or configured server name).',
                },
                'hostname': {
                    'type': 'string',
                    'description': 'Server hostname or IP address for SSH connections.',
                },
                'port': {
                    'type': 'number',
                    'description': 'SSH port number. Default: 22.',
                },
                'username': {
                    'type': 'string',
                    'description': 'SSH username. Default: root.',
                },
                'ssh_key_path': {
                    'type': 'string',
                    'description': 'Path to SSH private key file.',
                },
                'password': {
                    'type': 'string',
                    'description': 'SSH password (prefer SSH keys when possible).',
                },
                'command': {
                    'type': 'string',
                    'description': 'Command to execute on the remote server (ssh_execute operation).',
                },
                'local_path': {
                    'type': 'string',
                    'description': 'Local file path for upload/download operations.',
                },
                'remote_path': {
                    'type': 'string',
                    'description': 'Remote file path for upload/download operations.',
                },
                'local_port': {
                    'type': 'number',
                    'description': 'Local port for SSH tunnel.',
                },
                'remote_port': {
                    'type': 'number',
                    'description': 'Remote port for SSH tunnel.',
                },
                'gpu_type': {
                    'type': 'string',
                    'description': 'GPU type for cloud GPU instances (e.g., "NVIDIA RTX A6000", "NVIDIA A100 80GB").',
                },
                'gpu_count': {
                    'type': 'number',
                    'description': 'Number of GPUs for cloud instances.',
                },
                'docker_image': {
                    'type': 'string',
                    'description': 'Docker image to use for cloud GPU instances.',
                },
                'disk_size': {
                    'type': 'number',
                    'description': 'Disk size in GB for cloud instances.',
                },
                'process_id': {
                    'type': 'string',
                    'description': 'Process ID for kill_process operation.',
                },
                'service_name': {
                    'type': 'string',
                    'description': 'Service name for start_service/stop_service operations.',
                },
                'instance_id': {
                    'type': 'string',
                    'description': 'Cloud instance/pod ID for management operations.',
                },
                'api_key': {
                    'type': 'string',
                    'description': 'API key for cloud GPU platform authentication.',
                },
            },
            'required': ['operation'],
        },
    ),
)
