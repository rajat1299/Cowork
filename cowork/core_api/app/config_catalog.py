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
        "id": "lark",
        "name": "Lark",
        "icon": "lark",
        "toolkit": "lark_toolkit",
        "fields": [
            {"key": "LARK_APP_ID", "label": "App ID", "type": "text", "required": True},
            {"key": "LARK_APP_SECRET", "label": "App Secret", "type": "secret", "required": True},
        ],
    },
    {
        "id": "notion",
        "name": "Notion",
        "icon": "notion",
        "toolkit": "notion_mcp_toolkit",
        "fields": [
            {"key": "MCP_REMOTE_CONFIG_DIR", "label": "Remote Config Dir", "type": "text", "required": False},
        ],
    },
    {
        "id": "twitter",
        "name": "X(Twitter)",
        "icon": "twitter",
        "toolkit": "twitter_toolkit",
        "fields": [
            {"key": "TWITTER_CONSUMER_KEY", "label": "Consumer Key", "type": "secret", "required": True},
            {"key": "TWITTER_CONSUMER_SECRET", "label": "Consumer Secret", "type": "secret", "required": True},
            {"key": "TWITTER_ACCESS_TOKEN", "label": "Access Token", "type": "secret", "required": True},
            {
                "key": "TWITTER_ACCESS_TOKEN_SECRET",
                "label": "Access Token Secret",
                "type": "secret",
                "required": True,
            },
        ],
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp",
        "icon": "whatsapp",
        "toolkit": "whatsapp_toolkit",
        "fields": [
            {"key": "WHATSAPP_ACCESS_TOKEN", "label": "Access Token", "type": "secret", "required": True},
            {
                "key": "WHATSAPP_PHONE_NUMBER_ID",
                "label": "Phone Number ID",
                "type": "text",
                "required": True,
            },
        ],
    },
    {
        "id": "linkedin",
        "name": "LinkedIn",
        "icon": "linkedin",
        "toolkit": "linkedin_toolkit",
        "fields": [
            {"key": "LINKEDIN_ACCESS_TOKEN", "label": "Access Token", "type": "secret", "required": True},
        ],
    },
    {
        "id": "reddit",
        "name": "Reddit",
        "icon": "reddit",
        "toolkit": "reddit_toolkit",
        "fields": [
            {"key": "REDDIT_CLIENT_ID", "label": "Client ID", "type": "text", "required": True},
            {"key": "REDDIT_CLIENT_SECRET", "label": "Client Secret", "type": "secret", "required": True},
            {"key": "REDDIT_USER_AGENT", "label": "User Agent", "type": "text", "required": True},
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
        "id": "memory",
        "name": "Memory",
        "icon": "memory",
        "toolkit": "memory_toolkit",
        "fields": [
            {
                "key": "MEMORY_SEARCH_PAST_CHATS",
                "label": "Search past chats",
                "type": "text",
                "required": False,
            },
            {
                "key": "MEMORY_GENERATE_FROM_CHATS",
                "label": "Generate memory from chats",
                "type": "text",
                "required": False,
            },
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
    {
        "id": "google_calendar",
        "name": "Google Calendar",
        "icon": "google_calendar",
        "toolkit": "google_calendar_toolkit",
        "fields": [
            {"key": "GOOGLE_CLIENT_ID", "label": "Client ID", "type": "text", "required": True},
            {"key": "GOOGLE_CLIENT_SECRET", "label": "Client Secret", "type": "secret", "required": True},
            {"key": "GOOGLE_REFRESH_TOKEN", "label": "Refresh Token", "type": "secret", "required": True},
        ],
    },
    {
        "id": "google_drive_mcp",
        "name": "Google Drive MCP",
        "icon": "google_drive",
        "toolkit": "google_drive_mcp_toolkit",
        "fields": [],
    },
    {
        "id": "google_gmail_mcp",
        "name": "Google Gmail",
        "icon": "google_gmail",
        "toolkit": "google_gmail_native_toolkit",
        "fields": [
            {"key": "GOOGLE_CLIENT_ID", "label": "Client ID", "type": "text", "required": True},
            {"key": "GOOGLE_CLIENT_SECRET", "label": "Client Secret", "type": "secret", "required": True},
            {"key": "GOOGLE_REFRESH_TOKEN", "label": "Refresh Token", "type": "secret", "required": True},
        ],
    },
    {
        "id": "audio_analysis",
        "name": "Audio Analysis",
        "icon": "audio",
        "toolkit": "audio_analysis_toolkit",
        "fields": [],
    },
    {
        "id": "code_execution",
        "name": "Code Execution",
        "icon": "code",
        "toolkit": "code_execution_toolkit",
        "fields": [],
    },
    {
        "id": "craw4ai",
        "name": "Craw4ai",
        "icon": "craw4ai",
        "toolkit": "craw4ai_toolkit",
        "fields": [],
    },
    {
        "id": "dalle",
        "name": "Dall-E",
        "icon": "dalle",
        "toolkit": "dalle_toolkit",
        "fields": [],
    },
    {
        "id": "edgeone_pages_mcp",
        "name": "Edgeone Pages MCP",
        "icon": "edgeone_pages",
        "toolkit": "edgeone_pages_mcp_toolkit",
        "fields": [],
    },
    {
        "id": "excel",
        "name": "Excel",
        "icon": "excel",
        "toolkit": "excel_toolkit",
        "fields": [],
    },
    {
        "id": "file_write",
        "name": "File Write",
        "icon": "file_write",
        "toolkit": "file_write_toolkit",
        "fields": [],
    },
    {
        "id": "image_analysis",
        "name": "Image Analysis",
        "icon": "image",
        "toolkit": "image_analysis_toolkit",
        "fields": [],
    },
    {
        "id": "mcp_search",
        "name": "MCP Search",
        "icon": "mcp_search",
        "toolkit": "mcp_search_toolkit",
        "fields": [],
    },
    {
        "id": "pptx",
        "name": "PPTX",
        "icon": "pptx",
        "toolkit": "pptx_toolkit",
        "fields": [],
    },
]

CONFIG_CATALOG: dict[str, dict[str, list[str] | str]] = {
    "slack": {"env_vars": ["SLACK_BOT_TOKEN"], "toolkit": "slack_toolkit"},
    "lark": {"env_vars": ["LARK_APP_ID", "LARK_APP_SECRET"], "toolkit": "lark_toolkit"},
    "notion": {"env_vars": ["MCP_REMOTE_CONFIG_DIR"], "toolkit": "notion_mcp_toolkit"},
    "twitter": {
        "env_vars": [
            "TWITTER_CONSUMER_KEY",
            "TWITTER_CONSUMER_SECRET",
            "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_TOKEN_SECRET",
        ],
        "toolkit": "twitter_toolkit",
    },
    "whatsapp": {
        "env_vars": ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
        "toolkit": "whatsapp_toolkit",
    },
    "linkedin": {"env_vars": ["LINKEDIN_ACCESS_TOKEN"], "toolkit": "linkedin_toolkit"},
    "reddit": {
        "env_vars": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
        "toolkit": "reddit_toolkit",
    },
    "search": {
        "env_vars": ["GOOGLE_API_KEY", "SEARCH_ENGINE_ID", "EXA_API_KEY"],
        "toolkit": "search_toolkit",
    },
    "memory": {
        "env_vars": ["MEMORY_SEARCH_PAST_CHATS", "MEMORY_GENERATE_FROM_CHATS"],
        "toolkit": "memory_toolkit",
    },
    "github": {"env_vars": ["GITHUB_TOKEN"], "toolkit": "github_toolkit"},
    "google_calendar": {
        "env_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
        "toolkit": "google_calendar_toolkit",
    },
    "google_drive_mcp": {"env_vars": [], "toolkit": "google_drive_mcp_toolkit"},
    "google_gmail_mcp": {
        "env_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
        "toolkit": "google_gmail_native_toolkit",
    },
    "audio_analysis": {"env_vars": [], "toolkit": "audio_analysis_toolkit"},
    "code_execution": {"env_vars": [], "toolkit": "code_execution_toolkit"},
    "craw4ai": {"env_vars": [], "toolkit": "craw4ai_toolkit"},
    "dalle": {"env_vars": [], "toolkit": "dalle_toolkit"},
    "edgeone_pages_mcp": {"env_vars": [], "toolkit": "edgeone_pages_mcp_toolkit"},
    "excel": {"env_vars": [], "toolkit": "excel_toolkit"},
    "file_write": {"env_vars": [], "toolkit": "file_write_toolkit"},
    "image_analysis": {"env_vars": [], "toolkit": "image_analysis_toolkit"},
    "mcp_search": {"env_vars": [], "toolkit": "mcp_search_toolkit"},
    "pptx": {"env_vars": [], "toolkit": "pptx_toolkit"},
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
