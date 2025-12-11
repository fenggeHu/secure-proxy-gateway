class ConfigError(Exception):
    """Raised when configuration file is invalid or missing."""


class RouteNotFound(Exception):
    """Raised when no matching route is found for a request."""
