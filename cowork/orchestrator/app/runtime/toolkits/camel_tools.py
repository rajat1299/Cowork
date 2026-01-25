from __future__ import annotations

import logging
from typing import Any, Iterable

from camel.toolkits import FunctionTool
from camel.toolkits.code_execution import CodeExecutionToolkit
from camel.toolkits.file_toolkit import FileToolkit
from camel.toolkits.search_toolkit import SearchToolkit
from camel.toolkits.terminal_toolkit import TerminalToolkit

from app.runtime.toolkits.camel_listen import auto_listen_toolkit

logger = logging.getLogger(__name__)


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


SUPPORTED_TOOL_NAMES = {
    "search",
    "browser",
    "file",
    "terminal",
    "code_execution",
    "image",
    "audio",
    "video",
}

TOOL_ALIASES = {
    "docs": "file",
    "file_write": "file",
    "file_write_toolkit": "file",
    "file_toolkit": "file",
    "search_toolkit": "search",
    "browser_toolkit": "browser",
    "terminal_toolkit": "terminal",
    "code_execution_toolkit": "code_execution",
    "image_analysis_toolkit": "image",
    "audio_analysis_toolkit": "audio",
    "video_analysis_toolkit": "video",
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
) -> list[FunctionTool]:
    tools: list[FunctionTool] = []
    expanded = _normalize_tool_names(tool_names)

    if "search" in expanded:
        try:
            toolkit = SearchToolkitWithEvents(event_stream, agent_name=agent_name)
            _safe_extend(tools, toolkit.get_tools())
        except Exception as exc:
            logger.warning("Search toolkit unavailable: %s", exc)

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

    return tools
