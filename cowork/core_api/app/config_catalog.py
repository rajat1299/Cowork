CONFIG_CATALOG: dict[str, dict[str, list[str]]] = {
    "Slack": {"env_vars": ["SLACK_BOT_TOKEN"]},
    "Notion": {"env_vars": ["NOTION_TOKEN"]},
    "Search": {"env_vars": ["GOOGLE_API_KEY", "SEARCH_ENGINE_ID", "EXA_API_KEY"]},
    "Github": {"env_vars": ["GITHUB_TOKEN"]},
}


def list_catalog() -> dict[str, dict[str, list[str]]]:
    return CONFIG_CATALOG


def is_valid_env_var(group: str, name: str) -> bool:
    group_config = CONFIG_CATALOG.get(group)
    if not group_config:
        return False
    return name in group_config.get("env_vars", [])
