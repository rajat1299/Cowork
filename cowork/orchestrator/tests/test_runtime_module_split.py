import importlib

import pytest


MODULE_EXPORTS = {
    "app.runtime.tracing": ["_trace_log", "_trace_step"],
    "app.runtime.artifacts": ["_collect_tool_artifacts", "_extract_file_artifacts"],
    "app.runtime.memory": ["_build_context", "_compact_context", "_persist_message"],
    "app.runtime.context": ["_resolve_workdir", "_normalize_attachments", "_parse_summary"],
    "app.runtime.config_helpers": [
        "_env_flag",
        "_config_flag",
        "_requires_tool_permission",
        "_request_tool_permission",
    ],
    "app.runtime.mcp_config": ["_build_mcp_config", "_load_mcp_tools", "_normalize_mcp_args"],
    "app.runtime.task_analysis": ["_is_complex_task", "_detect_search_intent", "_extract_response"],
    "app.runtime.streaming": ["TokenTracker", "EventStream", "_emit"],
    "app.runtime.agents": ["CoworkSingleAgentWorker", "CoworkWorkforce", "_build_agent"],
    "app.runtime.executor": ["_run_camel_complex"],
    "app.runtime.camel_runtime": ["run_task_loop"],
}


@pytest.mark.parametrize(("module_name", "exports"), MODULE_EXPORTS.items())
def test_runtime_modules_export_expected_symbols(module_name: str, exports: list[str]) -> None:
    module = importlib.import_module(module_name)
    for symbol in exports:
        assert hasattr(module, symbol), f"{module_name} missing {symbol}"
