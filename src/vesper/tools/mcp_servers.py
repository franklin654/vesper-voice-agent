from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "mcp_servers.json"


def _expand_env(value):
    """Expands ${VAR}/$VAR placeholders against the current environment so
    secrets (e.g. PLAYWRIGHT_MCP_EXTENSION_TOKEN) live in .env, not in the
    checked-in JSON config."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {key: _expand_env(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_env(val) for val in value]
    return value


def get_mcp_client() -> MultiServerMCPClient:
    """Loads server configs from mcp_servers.json fresh on each call (rather
    than caching a module-level instance), so env var expansion always
    reflects the current environment regardless of import order relative to
    dotenv.load_dotenv()."""
    raw_config = json.loads(_CONFIG_PATH.read_text())
    return MultiServerMCPClient(_expand_env(raw_config))
