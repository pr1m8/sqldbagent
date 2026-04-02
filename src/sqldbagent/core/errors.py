"""Package error hierarchy."""


class SQLDBAgentError(Exception):
    """Base package error."""


class ConfigurationError(SQLDBAgentError):
    """Raised when settings or datasource definitions are invalid."""


class AdapterDependencyError(SQLDBAgentError):
    """Raised when an optional adapter dependency is missing."""
