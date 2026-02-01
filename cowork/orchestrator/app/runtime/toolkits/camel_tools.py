from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from typing import Any, Iterable

import httpx
from camel.toolkits import FunctionTool
from camel.toolkits.code_execution import CodeExecutionToolkit
from camel.toolkits.file_toolkit import FileToolkit
from camel.toolkits.search_toolkit import SearchToolkit
from camel.toolkits.terminal_toolkit import TerminalToolkit

from app.config import settings
from app.clients.core_api import search_chat_messages
from app.runtime.events import StepEvent
from app.runtime.tool_context import (
    current_agent_name,
    current_auth_token,
    current_process_task_id,
)
from app.runtime.toolkits.camel_listen import auto_listen_toolkit

logger = logging.getLogger(__name__)

# Thread-local storage for event loops used by sync tool wrappers
_thread_local = threading.local()


def _run_async_in_sync(coro):
    """Run an async coroutine from a synchronous context.
    
    Handles the case where async tools are invoked from sync callbacks
    (e.g., CAMEL's internal tool execution).
    """
    try:
        # First, try to get a running loop
        loop = asyncio.get_running_loop()
        # If we're here, there's a running loop but we're in a sync function
        # This shouldn't happen often, but handle it gracefully
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=60)
    except RuntimeError:
        # No running event loop - this is the normal case for sync wrappers
        # Use thread-local event loop for better performance
        if not hasattr(_thread_local, "loop") or _thread_local.loop.is_closed():
            _thread_local.loop = asyncio.new_event_loop()
        loop = _thread_local.loop
        try:
            return loop.run_until_complete(coro)
        except Exception:
            # If the loop is problematic, create a fresh one
            loop = asyncio.new_event_loop()
            _thread_local.loop = loop
            return loop.run_until_complete(coro)


def _coerce_limit(value: int | None, default: int = 5, max_limit: int = 20) -> int:
    try:
        limit = int(value) if value is not None else default
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, max_limit))


async def search_past_chats(
    query: str,
    project_id: str | None = None,
    task_id: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search past chat messages for the current user."""
    auth_token = current_auth_token.get()
    if not auth_token:
        return {"results": [], "count": 0, "error": "Missing auth token"}
    resolved_limit = _coerce_limit(limit)
    results = await search_chat_messages(
        auth_token,
        query,
        project_id=project_id,
        task_id=task_id,
        limit=resolved_limit,
    )
    return {"results": results, "count": len(results)}


async def search_exa(
    query: str,
    num_results: int = 3,
    search_type: str = "auto",
    category: str | None = None,
    include_text: list[str] | None = None,
    exclude_text: list[str] | None = None,
    use_autoprompt: bool | None = True,
) -> dict[str, Any]:
    """Search the web using server-paid Exa fallback."""
    auth_token = current_auth_token.get()
    if not auth_token:
        return {"results": [], "count": 0, "error": "Missing auth token"}
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return {"results": [], "count": 0, "error": "Missing core API URL"}
    capped_results = min(max(int(num_results), 1), 3)
    headers = {"Authorization": auth_token}
    if settings.core_api_internal_key:
        headers["X-Internal-Key"] = settings.core_api_internal_key
    payload = {
        "query": query,
        "search_type": search_type,
        "category": category,
        "num_results": capped_results,
        "include_text": include_text,
        "exclude_text": exclude_text,
        "use_autoprompt": use_autoprompt,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{base_url}/search/exa", json=payload, headers=headers)
            if resp.status_code in (402, 429):
                return {"results": [], "count": 0, "error": resp.json().get("detail")}
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        return {"results": [], "count": 0, "error": str(exc)}


@auto_listen_toolkit(SearchToolkit)
class SearchToolkitWithEvents(SearchToolkit):
    agent_name: str = "search_agent"

    def __init__(self, event_stream: Any, agent_name: str | None = None, **kwargs) -> None:
        self.event_stream = event_stream
        if agent_name:
            self.agent_name = agent_name
        super().__init__(**kwargs)


@auto_listen_toolkit(FileToolkit)
class FileToolkitWithEvents(FileToolkit):
    agent_name: str = "developer_agent"

    def __init__(
        self,
        event_stream: Any,
        agent_name: str | None = None,
        working_directory: str | None = None,
        **kwargs,
    ) -> None:
        self.event_stream = event_stream
        if agent_name:
            self.agent_name = agent_name
        super().__init__(working_directory=working_directory, **kwargs)


@auto_listen_toolkit(TerminalToolkit)
class TerminalToolkitWithEvents(TerminalToolkit):
    agent_name: str = "developer_agent"

    def __init__(
        self,
        event_stream: Any,
        agent_name: str | None = None,
        working_directory: str | None = None,
        **kwargs,
    ) -> None:
        self.event_stream = event_stream
        if agent_name:
            self.agent_name = agent_name
        super().__init__(working_directory=working_directory, **kwargs)

    def shell_exec(
        self,
        command: str,
        id: str | None = None,
        block: bool = True,
        timeout: float = 20.0,
    ) -> str:
        if id is None:
            import time
            id = f"auto_{int(time.time() * 1000)}"
        result = super().shell_exec(id=id, command=command, block=block, timeout=timeout)
        if block and result == "":
            return "Command executed successfully (no output)."
        return result


@auto_listen_toolkit(CodeExecutionToolkit)
class CodeExecutionToolkitWithEvents(CodeExecutionToolkit):
    agent_name: str = "developer_agent"

    def __init__(self, event_stream: Any, agent_name: str | None = None, **kwargs) -> None:
        self.event_stream = event_stream
        if agent_name:
            self.agent_name = agent_name
        super().__init__(**kwargs)


def _safe_extend(tools: list[FunctionTool], new_tools: Iterable[FunctionTool]) -> None:
    seen = {tool.func.__name__ for tool in tools}
    for tool in new_tools:
        if tool.func.__name__ in seen:
            continue
        tools.append(tool)
        seen.add(tool.func.__name__)


def _emit_tool_event(
    event_stream: Any,
    step: StepEvent,
    agent_name: str,
    process_task_id: str,
    toolkit_name: str,
    method_name: str,
    message: str,
) -> None:
    if event_stream is None:
        return
    event_stream.emit(
        step,
        {
            "agent_name": agent_name,
            "process_task_id": process_task_id,
            "toolkit_name": toolkit_name,
            "method_name": method_name.replace("_", " "),
            "message": message,
        },
    )


def _wrap_function_tool(
    tool: FunctionTool,
    event_stream: Any,
    agent_name: str,
    toolkit_name: str,
) -> FunctionTool:
    func = tool.func
    function_name = (
        tool.get_function_name()
        if hasattr(tool, "get_function_name")
        else getattr(func, "__name__", "tool")
    )
    method_name = function_name
    resolved_toolkit = toolkit_name
    if "__" in function_name and not toolkit_name:
        resolved_toolkit, method_name = function_name.split("__", 1)
    if not resolved_toolkit:
        resolved_toolkit = "mcp"

    async def _async_wrapper(*args, **kwargs):
        resolved_agent = agent_name or current_agent_name.get("")
        process_task_id = current_process_task_id.get("")
        _emit_tool_event(
            event_stream,
            StepEvent.activate_toolkit,
            resolved_agent,
            process_task_id,
            resolved_toolkit,
            method_name,
            f"args={args}, kwargs={kwargs}",
        )
        try:
            result = func(*args, **kwargs)
            if inspect.iscoroutine(result):
                result = await result
            _emit_tool_event(
                event_stream,
                StepEvent.deactivate_toolkit,
                resolved_agent,
                process_task_id,
                resolved_toolkit,
                method_name,
                str(result),
            )
            return result
        except Exception as exc:
            _emit_tool_event(
                event_stream,
                StepEvent.deactivate_toolkit,
                resolved_agent,
                process_task_id,
                resolved_toolkit,
                method_name,
                str(exc),
            )
            raise

    def _sync_wrapper(*args, **kwargs):
        resolved_agent = agent_name or current_agent_name.get("")
        process_task_id = current_process_task_id.get("")
        _emit_tool_event(
            event_stream,
            StepEvent.activate_toolkit,
            resolved_agent,
            process_task_id,
            resolved_toolkit,
            method_name,
            f"args={args}, kwargs={kwargs}",
        )
        try:
            result = func(*args, **kwargs)
            # Handle async functions called from sync context
            if inspect.iscoroutine(result):
                logger.debug(f"Running async tool {method_name} in sync context")
                result = _run_async_in_sync(result)
            _emit_tool_event(
                event_stream,
                StepEvent.deactivate_toolkit,
                resolved_agent,
                process_task_id,
                resolved_toolkit,
                method_name,
                str(result),
            )
            return result
        except Exception as exc:
            _emit_tool_event(
                event_stream,
                StepEvent.deactivate_toolkit,
                resolved_agent,
                process_task_id,
                resolved_toolkit,
                method_name,
                str(exc),
            )
            raise

    # Always use _sync_wrapper since it can handle both sync and async functions
    # This ensures tools work regardless of how CAMEL invokes them
    wrapper = _sync_wrapper
    wrapper.__name__ = getattr(func, "__name__", "tool")
    wrapper.__doc__ = getattr(func, "__doc__", None)
    return FunctionTool(wrapper, openai_tool_schema=tool.openai_tool_schema)


def _build_toolkit_tools(
    toolkit_cls: type,
    event_stream: Any,
    agent_name: str,
    **kwargs,
) -> list[FunctionTool]:
    @auto_listen_toolkit(toolkit_cls)
    class ToolkitWithEvents(toolkit_cls):
        def __init__(self, *args, **inner_kwargs) -> None:
            self.event_stream = event_stream
            self.agent_name = agent_name
            super().__init__(*args, **inner_kwargs)

    toolkit = ToolkitWithEvents(**kwargs)
    return toolkit.get_tools()


SUPPORTED_TOOL_NAMES = {
    "memory_search",
    "search",
    "browser",
    "hybrid_browser",
    "hybrid_browser_py",
    "file",
    "terminal",
    "code_execution",
    "image",
    "audio",
    "video",
    "audio_analysis",
    "image_analysis",
    "video_analysis",
    "video_download",
    "openai_image",
    "image_generation",
    "excel",
    "pptx",
    "github",
    "slack",
    "lark",
    "linkedin",
    "reddit",
    "twitter",
    "whatsapp",
    "google_calendar",
    "google_drive_mcp",
    "gmail",
    "notion",
    "notion_mcp",
    "mcp_search",
    "edgeone_pages_mcp",
    "craw4ai",
    "note_taking",
    "markitdown",
    "thinking",
    "pyautogui",
    "screenshot",
    "web_deploy",
    "mcp",
}

TOOL_ALIASES = {
    "docs": "file",
    "file_write": "file",
    "file_write_toolkit": "file",
    "file_toolkit": "file",
    "search_toolkit": "search",
    "search_past_chats": "memory_search",
    "browser_toolkit": "browser",
    "async_browser_toolkit": "browser",
    "hybrid_browser_toolkit": "hybrid_browser",
    "hybrid_browser_toolkit_py": "hybrid_browser_py",
    "terminal_toolkit": "terminal",
    "code_execution_toolkit": "code_execution",
    "image_analysis_toolkit": "image_analysis",
    "audio_analysis_toolkit": "audio_analysis",
    "video_analysis_toolkit": "video_analysis",
    "video_download_toolkit": "video_download",
    "openai_image_toolkit": "openai_image",
    "image_generation_toolkit": "image_generation",
    "dalle_toolkit": "openai_image",
    "excel_toolkit": "excel",
    "pptx_toolkit": "pptx",
    "github_toolkit": "github",
    "slack_toolkit": "slack",
    "lark_toolkit": "lark",
    "linkedin_toolkit": "linkedin",
    "reddit_toolkit": "reddit",
    "twitter_toolkit": "twitter",
    "whatsapp_toolkit": "whatsapp",
    "google_calendar_toolkit": "google_calendar",
    "google_drive_mcp_toolkit": "google_drive_mcp",
    "google_gmail_mcp_toolkit": "gmail",
    "google_gmail_native_toolkit": "gmail",
    "gmail_toolkit": "gmail",
    "notion_toolkit": "notion",
    "notion_mcp_toolkit": "notion_mcp",
    "mcp_search_toolkit": "mcp_search",
    "pulse_mcp_search_toolkit": "mcp_search",
    "edgeone_pages_mcp_toolkit": "edgeone_pages_mcp",
    "craw4ai_toolkit": "craw4ai",
    "note_taking_toolkit": "note_taking",
    "markitdown_toolkit": "markitdown",
    "thinking_toolkit": "thinking",
    "pyautogui_toolkit": "pyautogui",
    "screenshot_toolkit": "screenshot",
    "web_deploy_toolkit": "web_deploy",
    "mcp_toolkit": "mcp",
}


def _normalize_tool_names(tool_names: list[str]) -> set[str]:
    normalized = {name.strip().lower() for name in tool_names if name}
    expanded = {TOOL_ALIASES.get(name, name) for name in normalized}
    unsupported = sorted(expanded - SUPPORTED_TOOL_NAMES)
    if unsupported:
        logger.warning("Unsupported toolkit names requested: %s", ", ".join(unsupported))
    return expanded


def build_agent_tools(
    tool_names: list[str],
    event_stream: Any,
    agent_name: str,
    working_directory: str,
    mcp_tools: list[FunctionTool] | None = None,
    search_backend: str | None = None,
) -> list[FunctionTool]:
    tools: list[FunctionTool] = []
    expanded = _normalize_tool_names(tool_names)

    if "search" in expanded:
        if search_backend == "exa":
            try:
                tool = FunctionTool(search_exa)
                wrapped = _wrap_function_tool(tool, event_stream, agent_name, "search")
                _safe_extend(tools, [wrapped])
            except Exception as exc:
                logger.warning("Exa search toolkit unavailable: %s", exc)
        else:
            try:
                toolkit = SearchToolkitWithEvents(event_stream, agent_name=agent_name)
                _safe_extend(tools, toolkit.get_tools())
            except Exception as exc:
                logger.warning("Search toolkit unavailable: %s", exc)

    if "memory_search" in expanded:
        try:
            tool = FunctionTool(search_past_chats)
            wrapped = _wrap_function_tool(tool, event_stream, agent_name, "memory")
            _safe_extend(tools, [wrapped])
        except Exception as exc:
            logger.warning("Memory search toolkit unavailable: %s", exc)

    if "browser" in expanded:
        try:
            from camel.toolkits.browser_toolkit import BrowserToolkit
            from app.runtime.toolkits.camel_listen import auto_listen_toolkit as _auto

            @_auto(BrowserToolkit)
            class BrowserToolkitWithEvents(BrowserToolkit):
                def __init__(self, event_stream: Any, **kwargs) -> None:
                    self.event_stream = event_stream
                    self.agent_name = agent_name
                    super().__init__(**kwargs)

            toolkit = BrowserToolkitWithEvents(event_stream)
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Browser toolkit unavailable: %s", exc)

    if "file" in expanded:
        try:
            toolkit = FileToolkitWithEvents(
                event_stream,
                agent_name=agent_name,
                working_directory=working_directory,
            )
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("File toolkit unavailable: %s", exc)

    if "terminal" in expanded:
        try:
            toolkit = TerminalToolkitWithEvents(
                event_stream,
                agent_name=agent_name,
                working_directory=working_directory,
                safe_mode=True,
            )
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Terminal toolkit unavailable: %s", exc)

    if "code_execution" in expanded:
        try:
            toolkit = CodeExecutionToolkitWithEvents(
                event_stream,
                agent_name=agent_name,
                sandbox="subprocess",
                require_confirm=False,
            )
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Code execution toolkit unavailable: %s", exc)

    if "image" in expanded:
        try:
            from camel.toolkits.image_analysis_toolkit import ImageAnalysisToolkit
            from app.runtime.toolkits.camel_listen import auto_listen_toolkit as _auto

            @_auto(ImageAnalysisToolkit)
            class ImageToolkitWithEvents(ImageAnalysisToolkit):
                def __init__(self, event_stream: Any, **kwargs) -> None:
                    self.event_stream = event_stream
                    self.agent_name = agent_name
                    super().__init__(**kwargs)

            toolkit = ImageToolkitWithEvents(event_stream)
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Image toolkit unavailable: %s", exc)

    if "audio" in expanded:
        try:
            from camel.toolkits.audio_analysis_toolkit import AudioAnalysisToolkit
            from app.runtime.toolkits.camel_listen import auto_listen_toolkit as _auto

            @_auto(AudioAnalysisToolkit)
            class AudioToolkitWithEvents(AudioAnalysisToolkit):
                def __init__(self, event_stream: Any, **kwargs) -> None:
                    self.event_stream = event_stream
                    self.agent_name = agent_name
                    super().__init__(**kwargs)

            toolkit = AudioToolkitWithEvents(event_stream)
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Audio toolkit unavailable: %s", exc)

    if "video" in expanded:
        try:
            from camel.toolkits.video_analysis_toolkit import VideoAnalysisToolkit
            from app.runtime.toolkits.camel_listen import auto_listen_toolkit as _auto

            @_auto(VideoAnalysisToolkit)
            class VideoToolkitWithEvents(VideoAnalysisToolkit):
                def __init__(self, event_stream: Any, **kwargs) -> None:
                    self.event_stream = event_stream
                    self.agent_name = agent_name
                    super().__init__(**kwargs)

            toolkit = VideoToolkitWithEvents(event_stream)
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Video toolkit unavailable: %s", exc)

    if "audio_analysis" in expanded:
        try:
            from camel.toolkits.audio_analysis_toolkit import AudioAnalysisToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(AudioAnalysisToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Audio analysis toolkit unavailable: %s", exc)

    if "image_analysis" in expanded:
        try:
            from camel.toolkits.image_analysis_toolkit import ImageAnalysisToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(ImageAnalysisToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Image analysis toolkit unavailable: %s", exc)

    if "video_analysis" in expanded:
        try:
            from camel.toolkits.video_analysis_toolkit import VideoAnalysisToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(VideoAnalysisToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Video analysis toolkit unavailable: %s", exc)

    if "video_download" in expanded:
        try:
            from camel.toolkits.video_download_toolkit import VideoDownloaderToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(
                    VideoDownloaderToolkit,
                    event_stream,
                    agent_name,
                    working_directory=working_directory,
                ),
            )
        except Exception as exc:
            logger.warning("Video download toolkit unavailable: %s", exc)

    if "openai_image" in expanded:
        try:
            from camel.toolkits.image_generation_toolkit import OpenAIImageToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(OpenAIImageToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("OpenAI image toolkit unavailable: %s", exc)

    if "image_generation" in expanded:
        try:
            from camel.toolkits.image_generation_toolkit import ImageGenToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(ImageGenToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Image generation toolkit unavailable: %s", exc)

    if "excel" in expanded:
        try:
            from camel.toolkits.excel_toolkit import ExcelToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(ExcelToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Excel toolkit unavailable: %s", exc)

    if "pptx" in expanded:
        try:
            from camel.toolkits.pptx_toolkit import PPTXToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(PPTXToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("PPTX toolkit unavailable: %s", exc)

    if "github" in expanded:
        try:
            from camel.toolkits.github_toolkit import GithubToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(GithubToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("GitHub toolkit unavailable: %s", exc)

    if "slack" in expanded:
        try:
            from camel.toolkits.slack_toolkit import SlackToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(SlackToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Slack toolkit unavailable: %s", exc)

    if "lark" in expanded:
        try:
            from camel.toolkits.lark_toolkit import LarkToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(LarkToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Lark toolkit unavailable: %s", exc)

    if "linkedin" in expanded:
        try:
            from camel.toolkits.linkedin_toolkit import LinkedInToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(LinkedInToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("LinkedIn toolkit unavailable: %s", exc)

    if "reddit" in expanded:
        try:
            from camel.toolkits.reddit_toolkit import RedditToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(RedditToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Reddit toolkit unavailable: %s", exc)

    if "twitter" in expanded:
        try:
            from camel.toolkits.twitter_toolkit import TwitterToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(TwitterToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Twitter toolkit unavailable: %s", exc)

    if "whatsapp" in expanded:
        try:
            from camel.toolkits.whatsapp_toolkit import WhatsAppToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(WhatsAppToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("WhatsApp toolkit unavailable: %s", exc)

    if "google_calendar" in expanded:
        try:
            from camel.toolkits.google_calendar_toolkit import GoogleCalendarToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(GoogleCalendarToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Google Calendar toolkit unavailable: %s", exc)

    if "google_drive_mcp" in expanded:
        try:
            from camel.toolkits.google_drive_mcp_toolkit import GoogleDriveMCPToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(GoogleDriveMCPToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Google Drive MCP toolkit unavailable: %s", exc)

    if "gmail" in expanded:
        try:
            from camel.toolkits.gmail_toolkit import GmailToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(GmailToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Gmail toolkit unavailable: %s", exc)

    if "notion" in expanded:
        try:
            from camel.toolkits.notion_toolkit import NotionToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(NotionToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Notion toolkit unavailable: %s", exc)

    if "notion_mcp" in expanded:
        try:
            from camel.toolkits.notion_mcp_toolkit import NotionMCPToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(NotionMCPToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Notion MCP toolkit unavailable: %s", exc)

    if "mcp_search" in expanded:
        try:
            from camel.toolkits.pulse_mcp_search_toolkit import PulseMCPSearchToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(PulseMCPSearchToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("MCP search toolkit unavailable: %s", exc)

    if "edgeone_pages_mcp" in expanded:
        try:
            from camel.toolkits.edgeone_pages_mcp_toolkit import EdgeOnePagesMCPToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(EdgeOnePagesMCPToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("EdgeOne Pages MCP toolkit unavailable: %s", exc)

    if "craw4ai" in expanded:
        try:
            from camel.toolkits.craw4ai_toolkit import Crawl4AIToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(Crawl4AIToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Crawl4AI toolkit unavailable: %s", exc)

    if "note_taking" in expanded:
        try:
            from camel.toolkits.note_taking_toolkit import NoteTakingToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(
                    NoteTakingToolkit,
                    event_stream,
                    agent_name,
                    working_directory=working_directory,
                ),
            )
        except Exception as exc:
            logger.warning("Note taking toolkit unavailable: %s", exc)

    if "markitdown" in expanded:
        try:
            from camel.toolkits.markitdown_toolkit import MarkItDownToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(MarkItDownToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("MarkItDown toolkit unavailable: %s", exc)

    if "thinking" in expanded:
        try:
            from camel.toolkits.thinking_toolkit import ThinkingToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(ThinkingToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Thinking toolkit unavailable: %s", exc)

    if "pyautogui" in expanded:
        try:
            from camel.toolkits.pyautogui_toolkit import PyAutoGUIToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(PyAutoGUIToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("PyAutoGUI toolkit unavailable: %s", exc)

    if "screenshot" in expanded:
        try:
            from camel.toolkits.screenshot_toolkit import ScreenshotToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(
                    ScreenshotToolkit,
                    event_stream,
                    agent_name,
                    working_directory=working_directory,
                ),
            )
        except Exception as exc:
            logger.warning("Screenshot toolkit unavailable: %s", exc)

    if "web_deploy" in expanded:
        try:
            from camel.toolkits.web_deploy_toolkit import WebDeployToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(WebDeployToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Web deploy toolkit unavailable: %s", exc)

    if "hybrid_browser" in expanded:
        try:
            from camel.toolkits.hybrid_browser_toolkit import HybridBrowserToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(HybridBrowserToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Hybrid browser toolkit unavailable: %s", exc)

    if "hybrid_browser_py" in expanded:
        try:
            from camel.toolkits.hybrid_browser_toolkit_py import HybridBrowserToolkit

            _safe_extend(
                tools,
                _build_toolkit_tools(HybridBrowserToolkit, event_stream, agent_name),
            )
        except Exception as exc:
            logger.warning("Hybrid browser (py) toolkit unavailable: %s", exc)

    if "mcp" in expanded and mcp_tools:
        for tool in mcp_tools:
            try:
                wrapped = _wrap_function_tool(tool, event_stream, agent_name, "")
                _safe_extend(tools, [wrapped])
            except Exception as exc:
                logger.warning("MCP tool wrapper unavailable: %s", exc)

    return tools
