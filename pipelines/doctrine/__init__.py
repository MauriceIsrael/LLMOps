"""Deterministic doctrine engine: doctrine context packages and option judging.

No language model is used here: this package is served by the MCP/REST server.
"""

from pipelines.doctrine.context import build_doctrine_context
from pipelines.doctrine.index import DoctrineIndex, load_index
from pipelines.doctrine.judge import METHOD, check_option

__all__ = ["METHOD", "DoctrineIndex", "build_doctrine_context", "check_option", "load_index"]
