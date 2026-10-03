"""Typed exceptions for LLMOps MCP Server."""


class LLMOpsError(Exception):
    """Base exception for all domain and operational errors in LLMOps."""


class QueryRejectedError(LLMOpsError, PermissionError):
    """Raised when a Cypher query is rejected by security policy (read-only enforcement, keywords)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Query rejected: {reason}")


class SchemaError(LLMOpsError):
    """Raised when a table, property, or schema element does not exist in the graph database."""


class EngagementNotFoundError(LLMOpsError, FileNotFoundError):
    """Raised when an engagement database or identifier is not found on disk."""

    def __init__(self, engagement: str, message: str | None = None) -> None:
        self.engagement = engagement
        super().__init__(message or f"Engagement database not found for scope '{engagement}'")


class DatabaseError(LLMOpsError):
    """Raised on general database failure."""


# Aliases for backward compatibility and domain terminology
QueryRejected = QueryRejectedError
EngagementNotFound = EngagementNotFoundError



class InvalidEngagementIdError(LLMOpsError, ValueError):
    """Raised when an engagement identifier is not ``[a-z0-9-]+`` (path separators and dot segments included)."""

    def __init__(self, engagement: str) -> None:
        self.engagement = engagement
        super().__init__(
            f"Invalid engagement identifier '{engagement}'. Must contain only lowercase alphanumeric characters and hyphens."
        )
