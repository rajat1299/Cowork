from __future__ import annotations

import json
import logging
from pathlib import Path

from camel.toolkits.mcp_toolkit import MCPToolkit

from app.clients.core_api import fetch_mcp_users
from app.runtime.context import _sanitize_identifier


logger = logging.getLogger(__name__)


def _normalize_mcp_args(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return None


def _build_mcp_config(mcp_users: list[dict[str, object]]) -> dict[str, dict]:
    servers: dict[str, dict] = {}
    for item in mcp_users:
        status = item.get("status")
        if status and str(status).lower() != "enable":
            continue
        name = item.get("mcp_key") or item.get("mcp_name") or ""
        name = _sanitize_identifier(str(name), "mcp_server")
        mcp_type = str(item.get("mcp_type") or "local").lower()
        env = item.get("env") if isinstance(item.get("env"), dict) else {}
        if "MCP_REMOTE_CONFIG_DIR" not in env:
            env["MCP_REMOTE_CONFIG_DIR"] = str(Path.home() / ".cowork" / "mcp-auth")

        if mcp_type == "remote":
            server_url = item.get("server_url")
            if not server_url:
                continue
            servers[name] = {"url": server_url, "env": env}
            continue

        command = item.get("command")
        if not command:
            continue
        config: dict[str, object] = {"command": command}
        args = _normalize_mcp_args(item.get("args"))
        if args:
            config["args"] = args
        if env:
            config["env"] = env
        servers[name] = config

    return {"mcpServers": servers}


async def _load_mcp_tools(
    auth_token: str | None,
) -> tuple[MCPToolkit | None, list]:
    mcp_users = await fetch_mcp_users(auth_token)
    config = _build_mcp_config(mcp_users)
    if not config.get("mcpServers"):
        return None, []
    try:
        toolkit = MCPToolkit(config_dict=config, timeout=180)
        await toolkit.connect()
        return toolkit, toolkit.get_tools()
    except Exception as exc:
        logger.warning("MCP toolkit unavailable: %s", exc)
        return None, []
