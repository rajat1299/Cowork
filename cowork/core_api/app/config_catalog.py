CONFIG_GROUPS = [
    {
        "id": "slack",
        "name": "Slack",
        "icon": "slack",
        "toolkit": "slack_toolkit",
        "fields": [
            {"key": "SLACK_BOT_TOKEN", "label": "Bot Token", "type": "secret", "required": True},
        ],
    },
    {
        "id": "notion",
        "name": "Notion",
        "icon": "notion",
        "toolkit": "notion_mcp_toolkit",
        "fields": [
            {"key": "NOTION_TOKEN", "label": "Integration Token", "type": "secret", "required": True},
        ],
    },
    {
        "id": "search",
        "name": "Search",
        "icon": "search",
        "toolkit": "search_toolkit",
        "fields": [
            {"key": "GOOGLE_API_KEY", "label": "Google API Key", "type": "secret", "required": True},
            {"key": "SEARCH_ENGINE_ID", "label": "Search Engine ID", "type": "text", "required": True},
            {"key": "EXA_API_KEY", "label": "Exa API Key", "type": "secret", "required": False},
        ],
    },
    {
        "id": "github",
        "name": "GitHub",
        "icon": "github",
        "toolkit": "github_toolkit",
        "fields": [
            {"key": "GITHUB_TOKEN", "label": "Personal Access Token", "type": "secret", "required": True},
        ],
    },
]

CONFIG_CATALOG: dict[str, dict[str, list[str] | str]] = {
    "slack": {"env_vars": ["SLACK_BOT_TOKEN"], "toolkit": "slack_toolkit"},
    "notion": {"env_vars": ["NOTION_TOKEN"], "toolkit": "notion_mcp_toolkit"},
    "search": {
        "env_vars": ["GOOGLE_API_KEY", "SEARCH_ENGINE_ID", "EXA_API_KEY"],
        "toolkit": "search_toolkit",
    },
    "github": {"env_vars": ["GITHUB_TOKEN"], "toolkit": "github_toolkit"},
}


def list_catalog() -> dict[str, dict[str, list[str] | str] | list[dict[str, object]]]:
    return {
        "groups": CONFIG_GROUPS,
        "raw": CONFIG_CATALOG,
    }


def normalize_group(group: str | None) -> str | None:
    if not group:
        return None
    normalized = group.strip().lower()
    for entry in CONFIG_GROUPS:
        if normalized == entry["id"].lower() or normalized == entry["name"].lower():
            return entry["id"]
    return None


def group_aliases(group: str) -> list[str]:
    group_key = normalize_group(group)
    if not group_key:
        return []
    for entry in CONFIG_GROUPS:
        if entry["id"] == group_key:
            return [entry["id"], entry["name"]]
    return [group_key]


def is_valid_env_var(group: str, name: str) -> bool:
    group_key = normalize_group(group)
    if not group_key:
        return False
    group_config = CONFIG_CATALOG.get(group_key)
    if not group_config:
        return False
    env_vars = group_config.get("env_vars")
    if not isinstance(env_vars, list):
        return False
    return name in env_vars
