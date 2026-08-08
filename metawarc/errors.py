"""Domain exceptions used across metawarc interfaces."""


class MetawarcError(Exception):
    """Base class for user-facing metawarc errors."""


class WorkspaceError(MetawarcError):
    """Raised when an index workspace is missing or inconsistent."""


class SchemaCompatibilityError(WorkspaceError):
    """Raised when an index schema cannot be read safely."""


class WorkspaceLockedError(WorkspaceError):
    """Raised when another writer owns the workspace lock."""


class QueryValidationError(MetawarcError):
    """Raised when a typed query violates an allowlist or configured limit."""


class ExtractionLimitError(MetawarcError):
    """Raised when extraction exceeds a configured resource limit."""
