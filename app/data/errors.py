class RepositoryError(Exception):
    """Base error for data layer failures."""


class TransientRepositoryError(RepositoryError):
    """Retryable connection or warehouse errors."""


class UnsupportedAggregationError(RepositoryError):
    """Median or rate fields cannot roll up beyond block group."""


class ReadOnlyViolationError(RepositoryError):
    """SQL failed the read-only guard."""
