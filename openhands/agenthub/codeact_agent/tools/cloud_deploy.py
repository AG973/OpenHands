"""Cloud Deployment tool for the CodeAct Agent.

Provides the agent with deployment capabilities to AWS, GCP, Azure, RunPod,
and other cloud platforms. Uses CLI tools and REST APIs.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_CLOUD_DEPLOY_DESCRIPTION = """Deploy applications and manage cloud infrastructure on AWS, GCP, Azure, RunPod, and other platforms.

### Available Operations:

**AWS Operations:**
1. **aws_deploy_s3** - Deploy a static website or files to an S3 bucket.
2. **aws_deploy_lambda** - Deploy a function to AWS Lambda.
3. **aws_deploy_ec2** - Launch or manage an EC2 instance.
4. **aws_deploy_ecs** - Deploy a Docker container to ECS/Fargate.
5. **aws_configure** - Configure AWS credentials and region.

**GCP Operations:**
6. **gcp_deploy_cloud_run** - Deploy a container to Google Cloud Run.
7. **gcp_deploy_app_engine** - Deploy to Google App Engine.
8. **gcp_deploy_storage** - Deploy static files to Google Cloud Storage.
9. **gcp_configure** - Configure GCP project and credentials.

**Azure Operations:**
10. **azure_deploy_app_service** - Deploy to Azure App Service.
11. **azure_deploy_static** - Deploy a static website to Azure Static Web Apps.
12. **azure_deploy_container** - Deploy a container to Azure Container Instances.
13. **azure_configure** - Configure Azure subscription and credentials.

**RunPod Operations:**
14. **runpod_deploy_pod** - Deploy a GPU pod on RunPod.
15. **runpod_deploy_serverless** - Deploy a serverless GPU endpoint on RunPod.
16. **runpod_list_pods** - List running RunPod instances.
17. **runpod_stop_pod** - Stop a running RunPod instance.
18. **runpod_configure** - Configure RunPod API key.

**General Operations:**
19. **docker_build** - Build a Docker image from a Dockerfile.
20. **docker_push** - Push a Docker image to a container registry.
21. **deploy_status** - Check the deployment status of a service.
22. **list_deployments** - List all active deployments across platforms.

### Authentication:
- AWS: Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, or use aws_configure.
- GCP: Set GOOGLE_APPLICATION_CREDENTIALS or use gcp_configure.
- Azure: Use azure_configure or set AZURE_SUBSCRIPTION_ID and AZURE_TENANT_ID.
- RunPod: Set RUNPOD_API_KEY or use runpod_configure.

### Usage Notes:
- All deploy operations will build/package the application if needed before deploying.
- Docker operations require Docker to be installed in the runtime environment.
- Cloud CLI tools (aws, gcloud, az) will be installed on-demand if not present.
- Use deploy_status to monitor ongoing deployments.
"""

CloudDeployTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='cloud_deploy',
        description=_CLOUD_DEPLOY_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The cloud deployment operation to perform.',
                    'enum': [
                        'aws_deploy_s3',
                        'aws_deploy_lambda',
                        'aws_deploy_ec2',
                        'aws_deploy_ecs',
                        'aws_configure',
                        'gcp_deploy_cloud_run',
                        'gcp_deploy_app_engine',
                        'gcp_deploy_storage',
                        'gcp_configure',
                        'azure_deploy_app_service',
                        'azure_deploy_static',
                        'azure_deploy_container',
                        'azure_configure',
                        'runpod_deploy_pod',
                        'runpod_deploy_serverless',
                        'runpod_list_pods',
                        'runpod_stop_pod',
                        'runpod_configure',
                        'docker_build',
                        'docker_push',
                        'deploy_status',
                        'list_deployments',
                    ],
                },
                'platform': {
                    'type': 'string',
                    'description': 'Target cloud platform.',
                    'enum': ['aws', 'gcp', 'azure', 'runpod', 'docker'],
                },
                'project_path': {
                    'type': 'string',
                    'description': 'Path to the project or build directory to deploy.',
                },
                'service_name': {
                    'type': 'string',
                    'description': 'Name of the service/deployment.',
                },
                'region': {
                    'type': 'string',
                    'description': 'Cloud region to deploy to (e.g., "us-east-1", "us-central1", "eastus").',
                },
                'instance_type': {
                    'type': 'string',
                    'description': 'Instance/machine type (e.g., "t3.micro", "n1-standard-1", "NVIDIA A100").',
                },
                'docker_image': {
                    'type': 'string',
                    'description': 'Docker image name and tag (e.g., "myapp:latest").',
                },
                'dockerfile_path': {
                    'type': 'string',
                    'description': 'Path to the Dockerfile. Defaults to ./Dockerfile.',
                },
                'env_vars': {
                    'type': 'string',
                    'description': 'Environment variables as JSON string (e.g., \'{"KEY": "value"}\').',
                },
                'gpu_type': {
                    'type': 'string',
                    'description': 'GPU type for RunPod deployments (e.g., "NVIDIA RTX A6000", "NVIDIA A100 80GB").',
                },
                'gpu_count': {
                    'type': 'number',
                    'description': 'Number of GPUs for RunPod deployments.',
                },
                'api_key': {
                    'type': 'string',
                    'description': 'API key for cloud platform authentication (for configure operations).',
                },
                'deployment_id': {
                    'type': 'string',
                    'description': 'Deployment or pod ID for status checks and management.',
                },
                'role_arn': {
                    'type': 'string',
                    'description': 'IAM execution role ARN for AWS Lambda deployment (or set AWS_LAMBDA_ROLE_ARN env var).',
                },
            },
            'required': ['operation'],
        },
    ),
)
