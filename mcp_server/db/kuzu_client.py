"""Compatibility shim for KuzuClient redirecting to LadybugClient."""

from mcp_server.db.ladybug_client import LadybugClient

# Backward compatibility alias
KuzuClient = LadybugClient

__all__ = ["KuzuClient", "LadybugClient"]
