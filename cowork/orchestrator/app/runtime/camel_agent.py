from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

from camel.agents import ChatAgent
from camel.agents._types import ModelResponse, ToolCallRequest
from camel.agents._utils import handle_logprobs, safe_model_dump
from camel.messages import BaseMessage
from camel.types import ChatCompletion

logger = logging.getLogger(__name__)


def _truncate(value: str, max_len: int = 200) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}... (truncated)"


def _extract_json_candidate(raw: str) -> str:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.IGNORECASE).strip()
        if candidate.endswith("```"):
            candidate = candidate[:-3].strip()
    brace_start = candidate.find("{")
    brace_end = candidate.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return candidate[brace_start : brace_end + 1]
    bracket_start = candidate.find("[")
    bracket_end = candidate.rfind("]")
    if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
        return candidate[bracket_start : bracket_end + 1]
    return candidate


def _safe_tool_args(raw: Any, tool_name: str, tool_call_id: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    if isinstance(raw, (list, tuple)):
        return {"items": list(raw)}
    if not isinstance(raw, str):
        return {"value": raw}

    text = raw.strip()
    if not text:
        return {}

    candidate = _extract_json_candidate(text)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

    for attempt in (candidate, text):
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
        return {"value": parsed}

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, (list, tuple)):
            return {"items": list(parsed)}
        return {"value": parsed}
    except Exception:
        logger.warning(
            "Tool call args parse failed for %s (%s): %s",
            tool_name,
            tool_call_id,
            _truncate(text),
        )
        return {}


class CoworkChatAgent(ChatAgent):
    def _handle_batch_response(self, response: ChatCompletion) -> ModelResponse:
        output_messages: list[BaseMessage] = []
        for choice in response.choices:
            if (
                choice.message.content is None
                or choice.message.content.strip() == ""
            ) and not choice.message.tool_calls:
                continue

            meta_dict: dict[str, Any] = {}
            if logprobs_info := handle_logprobs(choice):
                meta_dict["logprobs_info"] = logprobs_info

            reasoning_content = getattr(choice.message, "reasoning_content", None)

            chat_message = BaseMessage(
                role_name=self.role_name,
                role_type=self.role_type,
                meta_dict=meta_dict,
                content=choice.message.content or "",
                parsed=getattr(choice.message, "parsed", None),
                reasoning_content=reasoning_content,
            )

            output_messages.append(chat_message)

        finish_reasons = [
            str(choice.finish_reason) for choice in response.choices
        ]

        usage: dict[str, Any] = {}
        if response.usage is not None:
            usage = safe_model_dump(response.usage)

        tool_call_requests: list[ToolCallRequest] | None = None
        if tool_calls := response.choices[0].message.tool_calls:
            tool_call_requests = []
            for tool_call in tool_calls:
                tool_name = tool_call.function.name  # type: ignore[union-attr]
                tool_call_id = tool_call.id
                args = _safe_tool_args(tool_call.function.arguments, tool_name, tool_call_id)  # type: ignore[union-attr]
                extra_content = getattr(tool_call, "extra_content", None)

                tool_call_request = ToolCallRequest(
                    tool_name=tool_name,
                    args=args,
                    tool_call_id=tool_call_id,
                    extra_content=extra_content,
                )
                tool_call_requests.append(tool_call_request)

        return ModelResponse(
            response=response,
            tool_call_requests=tool_call_requests,
            output_messages=output_messages,
            finish_reasons=finish_reasons,
            usage_dict=usage,
            response_id=response.id or "",
        )
