"""Domain exceptions for ServerKit."""


class ServerKitError(Exception):
    """Base exception for all SDK errors."""


class ProcessNotFound(ServerKitError):
    """Raised when a process PID does not exist."""


class WorkflowNotFound(ServerKitError):
    """Raised when a workflow file is missing."""


class LogFileNotFound(ServerKitError):
    """Raised when a log path cannot be read."""


class ServiceNotFound(ServerKitError):
    """Raised when a systemd unit is not found."""


class ContainerNotFound(ServerKitError):
    """Raised when a Docker container is not found."""


class WorkflowValidationError(ServerKitError):
    """Raised when workflow JSON or steps fail validation."""


class StepExecutionError(ServerKitError):
    """Raised when a workflow step fails at runtime."""


class ConfigurationError(ServerKitError):
    """Raised when config is invalid or unreadable."""


class OptionalDependencyError(ServerKitError):
    """Raised when an optional extra (rich, docker, remote) is not installed."""


class RemoteConnectionError(ServerKitError):
    """Raised when SSH connect or remote command execution fails."""


class ExternalCommandNotFound(ServerKitError):
    """A required host binary (e.g. systemctl, who) is missing — typical on non-Linux."""
