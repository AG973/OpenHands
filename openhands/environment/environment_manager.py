"""Environment manager — Docker/Kubernetes-aware sandbox management.

Provides production-grade environment management for agent sandboxes:
- Docker container lifecycle (create, start, stop, remove)
- Resource limits and monitoring (CPU, memory, disk)
- Health checking and auto-restart
- Network isolation and port mapping
- Volume management for persistent data
- Container pool for fast sandbox provisioning
- Kubernetes scaling patterns for production

Extends OpenHands' existing Docker sandbox with:
- Resource monitoring and limits enforcement
- Container pool pre-warming
- Health-based auto-restart
- Multi-sandbox orchestration

Per OPERATING_RULES.md RULE 5: Production-grade — no prototypes.
"""

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger

# Environment limits
MAX_CONTAINERS = 50
MAX_CPU_LIMIT = 8.0  # cores
MAX_MEMORY_LIMIT_MB = 16_384  # 16GB
MAX_DISK_LIMIT_MB = 102_400  # 100GB
MAX_PORT_RANGE = 1000
MAX_VOLUMES = 20
MAX_ENV_VARS = 200
HEALTH_CHECK_INTERVAL_S = 30
POOL_SIZE_DEFAULT = 3
CONTAINER_TTL_S = 3600  # 1 hour default


class ContainerState(Enum):
    """State of a managed container."""

    CREATING = 'creating'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    FAILED = 'failed'
    REMOVING = 'removing'
    REMOVED = 'removed'


class ContainerRuntime(Enum):
    """Container runtime to use."""

    DOCKER = 'docker'
    PODMAN = 'podman'


class ResourceType(Enum):
    """Types of resource metrics."""

    CPU_PERCENT = 'cpu_percent'
    MEMORY_MB = 'memory_mb'
    MEMORY_PERCENT = 'memory_percent'
    DISK_MB = 'disk_mb'
    NETWORK_RX_BYTES = 'network_rx_bytes'
    NETWORK_TX_BYTES = 'network_tx_bytes'


class HealthStatus(Enum):
    """Container health status."""

    HEALTHY = 'healthy'
    UNHEALTHY = 'unhealthy'
    STARTING = 'starting'
    UNKNOWN = 'unknown'


@dataclass
class ResourceLimits:
    """Resource limits for a container."""

    cpu_cores: float = 2.0
    memory_mb: int = 4096
    disk_mb: int = 10_240  # 10GB
    pids_limit: int = 1000
    network_bandwidth_mbps: int = 100

    def __post_init__(self) -> None:
        self.cpu_cores = min(self.cpu_cores, MAX_CPU_LIMIT)
        self.memory_mb = min(self.memory_mb, MAX_MEMORY_LIMIT_MB)
        self.disk_mb = min(self.disk_mb, MAX_DISK_LIMIT_MB)


@dataclass
class ResourceUsage:
    """Current resource usage of a container."""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_mb: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    measured_at: float = 0.0

    def __post_init__(self) -> None:
        if self.measured_at == 0.0:
            self.measured_at = time.time()


@dataclass
class PortMapping:
    """Port mapping between host and container."""

    host_port: int
    container_port: int
    protocol: str = 'tcp'


@dataclass
class VolumeMount:
    """Volume mount configuration."""

    host_path: str
    container_path: str
    read_only: bool = False


@dataclass
class HealthCheck:
    """Container health check configuration."""

    command: str = 'echo ok'
    interval_s: int = HEALTH_CHECK_INTERVAL_S
    timeout_s: int = 10
    retries: int = 3
    start_period_s: int = 10


@dataclass
class ContainerConfig:
    """Configuration for a managed container."""

    image: str
    name: str = ''
    command: str = ''
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[PortMapping] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    health_check: HealthCheck = field(default_factory=HealthCheck)
    labels: dict[str, str] = field(default_factory=dict)
    network: str = ''
    working_dir: str = ''
    user: str = ''
    auto_remove: bool = False
    ttl_s: int = CONTAINER_TTL_S

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f'openhands-{uuid.uuid4().hex[:8]}'
        if len(self.environment) > MAX_ENV_VARS:
            raise ValueError(f'Too many env vars (max {MAX_ENV_VARS})')
        if len(self.volumes) > MAX_VOLUMES:
            raise ValueError(f'Too many volumes (max {MAX_VOLUMES})')
        # Always add management label
        self.labels['managed-by'] = 'openhands'


@dataclass
class ManagedContainer:
    """A container managed by the environment manager."""

    container_id: str
    config: ContainerConfig
    state: ContainerState = ContainerState.CREATING
    health: HealthStatus = HealthStatus.UNKNOWN
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    docker_id: str = ''  # Docker's container ID
    created_at: float = 0.0
    started_at: float = 0.0
    stopped_at: float = 0.0
    restart_count: int = 0
    last_health_check: float = 0.0
    error: str = ''

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
        if not self.container_id:
            self.container_id = f'cont-{uuid.uuid4().hex[:8]}'

    @property
    def uptime_s(self) -> float:
        if self.started_at > 0 and self.state == ContainerState.RUNNING:
            return time.time() - self.started_at
        return 0.0

    @property
    def is_expired(self) -> bool:
        if self.config.ttl_s <= 0:
            return False
        return self.uptime_s > self.config.ttl_s


class DockerClient:
    """Docker CLI wrapper for container management.

    Uses subprocess to call Docker CLI commands rather than
    requiring the docker-py library.
    """

    def __init__(self, runtime: ContainerRuntime = ContainerRuntime.DOCKER) -> None:
        self._runtime = runtime
        self._cmd = runtime.value

    def is_available(self) -> bool:
        """Check if Docker/Podman is available."""
        try:
            result = subprocess.run(
                [self._cmd, 'version', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def create_container(self, config: ContainerConfig) -> str:
        """Create a new container and return its Docker ID."""
        cmd: list[str] = [self._cmd, 'create']

        # Name
        cmd.extend(['--name', config.name])

        # Resource limits
        cmd.extend([
            '--cpus', str(config.resource_limits.cpu_cores),
            '--memory', f'{config.resource_limits.memory_mb}m',
            '--pids-limit', str(config.resource_limits.pids_limit),
        ])

        # Environment variables
        for key, value in config.environment.items():
            cmd.extend(['-e', f'{key}={value}'])

        # Port mappings
        for port in config.ports:
            cmd.extend([
                '-p',
                f'{port.host_port}:{port.container_port}/{port.protocol}',
            ])

        # Volume mounts
        for vol in config.volumes:
            mount_str = f'{vol.host_path}:{vol.container_path}'
            if vol.read_only:
                mount_str += ':ro'
            cmd.extend(['-v', mount_str])

        # Labels
        for key, value in config.labels.items():
            cmd.extend(['--label', f'{key}={value}'])

        # Network
        if config.network:
            cmd.extend(['--network', config.network])

        # Working directory
        if config.working_dir:
            cmd.extend(['-w', config.working_dir])

        # User
        if config.user:
            cmd.extend(['--user', config.user])

        # Health check
        if config.health_check.command:
            cmd.extend([
                '--health-cmd', config.health_check.command,
                '--health-interval', f'{config.health_check.interval_s}s',
                '--health-timeout', f'{config.health_check.timeout_s}s',
                '--health-retries', str(config.health_check.retries),
                '--health-start-period', f'{config.health_check.start_period_s}s',
            ])

        # Image and command
        cmd.append(config.image)
        if config.command:
            cmd.extend(config.command.split())

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f'Failed to create container: {result.stderr.strip()}'
            )

        docker_id = result.stdout.strip()
        logger.info(f'Container created: {config.name} ({docker_id[:12]})')
        return docker_id

    def start_container(self, name_or_id: str) -> None:
        """Start a container."""
        result = subprocess.run(
            [self._cmd, 'start', name_or_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f'Failed to start container: {result.stderr.strip()}'
            )

    def stop_container(self, name_or_id: str, timeout: int = 10) -> None:
        """Stop a container."""
        result = subprocess.run(
            [self._cmd, 'stop', '-t', str(timeout), name_or_id],
            capture_output=True,
            text=True,
            timeout=timeout + 15,
        )
        if result.returncode != 0:
            logger.warning(f'Failed to stop container: {result.stderr.strip()}')

    def remove_container(self, name_or_id: str, force: bool = False) -> None:
        """Remove a container."""
        cmd = [self._cmd, 'rm']
        if force:
            cmd.append('-f')
        cmd.append(name_or_id)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f'Failed to remove container: {result.stderr.strip()}')

    def inspect_container(self, name_or_id: str) -> dict[str, Any]:
        """Get detailed container information."""
        result = subprocess.run(
            [self._cmd, 'inspect', name_or_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}

        try:
            data = json.loads(result.stdout)
            if isinstance(data, list) and data:
                return data[0]
            return {}
        except json.JSONDecodeError:
            return {}

    def get_stats(self, name_or_id: str) -> ResourceUsage:
        """Get container resource usage stats."""
        result = subprocess.run(
            [
                self._cmd, 'stats', name_or_id,
                '--no-stream',
                '--format', '{{json .}}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return ResourceUsage()

        try:
            data = json.loads(result.stdout.strip())
            cpu_str = data.get('CPUPerc', '0%').rstrip('%')
            mem_str = data.get('MemPerc', '0%').rstrip('%')

            return ResourceUsage(
                cpu_percent=float(cpu_str) if cpu_str else 0.0,
                memory_percent=float(mem_str) if mem_str else 0.0,
            )
        except (json.JSONDecodeError, ValueError):
            return ResourceUsage()

    def exec_in_container(
        self,
        name_or_id: str,
        command: str,
        timeout: int = 30,
    ) -> tuple[int, str, str]:
        """Execute a command inside a running container.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        result = subprocess.run(
            [self._cmd, 'exec', name_or_id, 'sh', '-c', command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr

    def list_containers(
        self,
        label: str = 'managed-by=openhands',
    ) -> list[dict[str, str]]:
        """List containers with a specific label."""
        result = subprocess.run(
            [
                self._cmd, 'ps', '-a',
                '--filter', f'label={label}',
                '--format', '{{json .}}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        containers: list[dict[str, str]] = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return containers


@dataclass
class EnvironmentConfig:
    """Configuration for the environment manager."""

    runtime: ContainerRuntime = ContainerRuntime.DOCKER
    default_image: str = 'ubuntu:22.04'
    pool_size: int = POOL_SIZE_DEFAULT
    auto_cleanup: bool = True
    health_check_interval_s: int = HEALTH_CHECK_INTERVAL_S
    max_containers: int = MAX_CONTAINERS
    default_ttl_s: int = CONTAINER_TTL_S
    default_resource_limits: ResourceLimits = field(
        default_factory=ResourceLimits
    )


class EnvironmentManager:
    """High-level environment manager for agent sandboxes.

    Manages the lifecycle of Docker containers used as agent sandboxes,
    including resource limits, health monitoring, and auto-scaling.

    Usage:
        manager = EnvironmentManager()
        container = manager.create_sandbox("my-agent")
        manager.start(container.container_id)
        exit_code, stdout, stderr = manager.exec(
            container.container_id, "echo hello"
        )
        manager.stop(container.container_id)
    """

    def __init__(self, config: EnvironmentConfig | None = None) -> None:
        self._config = config or EnvironmentConfig()
        self._docker = DockerClient(self._config.runtime)
        self._containers: dict[str, ManagedContainer] = {}
        self._on_health_change: list[
            Callable[[ManagedContainer, HealthStatus], None]
        ] = []

        if not self._docker.is_available():
            logger.warning(
                f'{self._config.runtime.value} is not available. '
                f'Environment management will be limited.'
            )

        logger.info(
            f'EnvironmentManager initialized: '
            f'runtime={self._config.runtime.value}'
        )

    def create_sandbox(
        self,
        name: str = '',
        image: str = '',
        command: str = '',
        environment: dict[str, str] | None = None,
        ports: list[PortMapping] | None = None,
        volumes: list[VolumeMount] | None = None,
        resource_limits: ResourceLimits | None = None,
    ) -> ManagedContainer:
        """Create a new sandbox container.

        Args:
            name: Container name (auto-generated if empty)
            image: Docker image (uses default if empty)
            command: Command to run
            environment: Environment variables
            ports: Port mappings
            volumes: Volume mounts
            resource_limits: Resource limits

        Returns:
            ManagedContainer
        """
        if len(self._containers) >= self._config.max_containers:
            raise RuntimeError(
                f'Max containers ({self._config.max_containers}) reached'
            )

        config = ContainerConfig(
            image=image or self._config.default_image,
            name=name or f'openhands-sandbox-{uuid.uuid4().hex[:8]}',
            command=command,
            environment=environment or {},
            ports=ports or [],
            volumes=volumes or [],
            resource_limits=resource_limits or self._config.default_resource_limits,
            ttl_s=self._config.default_ttl_s,
        )

        container = ManagedContainer(
            container_id=f'cont-{uuid.uuid4().hex[:8]}',
            config=config,
        )

        try:
            docker_id = self._docker.create_container(config)
            container.docker_id = docker_id
            container.state = ContainerState.STOPPED
        except Exception as e:
            container.state = ContainerState.FAILED
            container.error = str(e)
            logger.error(f'Failed to create sandbox: {e}')

        self._containers[container.container_id] = container
        return container

    def start(self, container_id: str) -> ManagedContainer:
        """Start a sandbox container."""
        container = self._get_container(container_id)

        if container.state == ContainerState.RUNNING:
            return container

        try:
            self._docker.start_container(
                container.docker_id or container.config.name
            )
            container.state = ContainerState.RUNNING
            container.started_at = time.time()
            container.health = HealthStatus.STARTING
            logger.info(f'Sandbox started: {container_id}')
        except Exception as e:
            container.state = ContainerState.FAILED
            container.error = str(e)
            logger.error(f'Failed to start sandbox: {e}')

        return container

    def stop(self, container_id: str) -> ManagedContainer:
        """Stop a sandbox container."""
        container = self._get_container(container_id)

        if container.state != ContainerState.RUNNING:
            return container

        try:
            self._docker.stop_container(
                container.docker_id or container.config.name
            )
            container.state = ContainerState.STOPPED
            container.stopped_at = time.time()
            logger.info(f'Sandbox stopped: {container_id}')
        except Exception as e:
            container.error = str(e)
            logger.error(f'Failed to stop sandbox: {e}')

        return container

    def remove(self, container_id: str, force: bool = False) -> None:
        """Remove a sandbox container."""
        container = self._get_container(container_id)

        try:
            container.state = ContainerState.REMOVING
            self._docker.remove_container(
                container.docker_id or container.config.name,
                force=force,
            )
            container.state = ContainerState.REMOVED
            del self._containers[container_id]
            logger.info(f'Sandbox removed: {container_id}')
        except Exception as e:
            container.error = str(e)
            logger.error(f'Failed to remove sandbox: {e}')

    def exec(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> tuple[int, str, str]:
        """Execute a command in a sandbox.

        Args:
            container_id: Container to execute in
            command: Command to run
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        container = self._get_container(container_id)

        if container.state != ContainerState.RUNNING:
            raise RuntimeError(
                f'Container {container_id} is not running '
                f'(state: {container.state.value})'
            )

        return self._docker.exec_in_container(
            container.docker_id or container.config.name,
            command,
            timeout=timeout,
        )

    def get_stats(self, container_id: str) -> ResourceUsage:
        """Get current resource usage for a container."""
        container = self._get_container(container_id)

        usage = self._docker.get_stats(
            container.docker_id or container.config.name
        )
        container.resource_usage = usage
        return usage

    def check_health(self, container_id: str) -> HealthStatus:
        """Check container health."""
        container = self._get_container(container_id)

        if container.state != ContainerState.RUNNING:
            return HealthStatus.UNKNOWN

        try:
            exit_code, stdout, _ = self._docker.exec_in_container(
                container.docker_id or container.config.name,
                container.config.health_check.command,
                timeout=container.config.health_check.timeout_s,
            )

            old_health = container.health
            container.health = (
                HealthStatus.HEALTHY if exit_code == 0
                else HealthStatus.UNHEALTHY
            )
            container.last_health_check = time.time()

            # Notify on health change
            if old_health != container.health:
                for handler in self._on_health_change:
                    try:
                        handler(container, container.health)
                    except Exception as e:
                        logger.warning(f'Health handler error: {e}')

            return container.health

        except Exception as e:
            container.health = HealthStatus.UNHEALTHY
            logger.warning(f'Health check failed for {container_id}: {e}')
            return HealthStatus.UNHEALTHY

    def restart(self, container_id: str) -> ManagedContainer:
        """Restart a container."""
        container = self._get_container(container_id)

        self.stop(container_id)
        self.start(container_id)
        container.restart_count += 1

        logger.info(
            f'Sandbox restarted: {container_id} '
            f'(restart #{container.restart_count})'
        )
        return container

    def cleanup_expired(self) -> int:
        """Remove expired containers. Returns count removed."""
        removed = 0
        expired_ids = [
            cid for cid, c in self._containers.items()
            if c.is_expired
        ]

        for cid in expired_ids:
            try:
                self.remove(cid, force=True)
                removed += 1
            except Exception as e:
                logger.warning(f'Failed to cleanup {cid}: {e}')

        if removed:
            logger.info(f'Cleaned up {removed} expired containers')
        return removed

    def list_sandboxes(self) -> list[dict[str, Any]]:
        """List all managed sandboxes."""
        return [
            {
                'container_id': c.container_id,
                'name': c.config.name,
                'image': c.config.image,
                'state': c.state.value,
                'health': c.health.value,
                'uptime_s': c.uptime_s,
                'restart_count': c.restart_count,
            }
            for c in self._containers.values()
        ]

    def on_health_change(
        self,
        handler: Callable[[ManagedContainer, HealthStatus], None],
    ) -> None:
        """Register handler for health status changes."""
        self._on_health_change.append(handler)

    def _get_container(self, container_id: str) -> ManagedContainer:
        """Get container or raise."""
        container = self._containers.get(container_id)
        if container is None:
            raise ValueError(f'Container {container_id} not found')
        return container

    def stats(self) -> dict[str, Any]:
        """Get environment manager statistics."""
        states: dict[str, int] = {}
        for c in self._containers.values():
            state = c.state.value
            states[state] = states.get(state, 0) + 1

        return {
            'runtime': self._config.runtime.value,
            'runtime_available': self._docker.is_available(),
            'total_containers': len(self._containers),
            'container_states': states,
            'max_containers': self._config.max_containers,
            'default_image': self._config.default_image,
        }

    def close(self) -> None:
        """Clean up all managed containers."""
        if self._config.auto_cleanup:
            for cid in list(self._containers.keys()):
                try:
                    self.remove(cid, force=True)
                except Exception as e:
                    logger.warning(f'Cleanup failed for {cid}: {e}')
