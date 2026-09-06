"""Configuration centralisée du serveur FastMCP (module de compatibilité unifié)."""

from mcp_server.core.config import ServerConfig, server_config

# Aliases pour compatibilité ascendante stricte
Settings = ServerConfig
settings = server_config


