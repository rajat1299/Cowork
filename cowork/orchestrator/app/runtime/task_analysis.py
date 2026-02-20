from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from camel.agents.chat_agent import AsyncStreamingChatAgentResponse

from app.clients.core_api import ProviderConfig, SkillEntry
from app.runtime.actions import AgentSpec
from app.runtime.llm_client import (
    _ANTHROPIC_NAMES,
    _OPENAI_COMPAT_DEFAULTS,
    _OPENAI_COMPAT_REQUIRES_ENDPOINT,
    _normalize_provider_name,
    collect_chat_completion,
)
from app.runtime.memory import _usage_total
from app.runtime.skills import RuntimeSkill
from app.runtime.skills_schema import load_skill_packs
from app.runtime.skill_catalog_matching import catalog_skill_matches_request
from app.runtime.workforce import AgentProfile, build_complexity_prompt


def _agent_profile_from_spec(spec: AgentSpec) -> AgentProfile:
    name = (spec.name or "").strip()
    description = (spec.description or "").strip()
    system_prompt = (spec.system_prompt or "").strip()
    if not system_prompt:
        if description:
            system_prompt = f"You are {description}."
        else:
            system_prompt = f"You are {name}."
        system_prompt = f"{system_prompt} Use tools when needed. Be concise and actionable."
    if not description:
        description = f"{name} agent"
    return AgentProfile(
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=list(spec.tools or []),
    )


def _merge_agent_specs(
    defaults: list[AgentProfile],
    custom_specs: list[AgentSpec] | None,
) -> list[AgentProfile]:
    if not custom_specs:
        return defaults
    merged = list(defaults)
    for spec in custom_specs:
        name = (spec.name or "").strip()
        if not name:
            continue
        profile = _agent_profile_from_spec(spec)
        replaced = False
        for index, existing in enumerate(merged):
            if existing.name.lower() == name.lower():
                merged[index] = profile
                replaced = True
                break
        if not replaced:
            merged.append(profile)
    return merged


def _ensure_tool(agent_specs: list[AgentProfile], tool_name: str) -> None:
    for spec in agent_specs:
        if tool_name not in spec.tools:
            spec.tools.append(tool_name)


def _resolve_model_url(provider: ProviderConfig) -> str | None:
    if provider.endpoint_url:
        return provider.endpoint_url
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _OPENAI_COMPAT_DEFAULTS:
        return _OPENAI_COMPAT_DEFAULTS[normalized]
    if normalized in _OPENAI_COMPAT_REQUIRES_ENDPOINT:
        raise ValueError("Endpoint URL required for OpenAI-compatible provider")
    return None


def _build_native_search_params(provider: ProviderConfig) -> dict[str, Any] | None:
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _ANTHROPIC_NAMES:
        return {
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }
            ]
        }
    if normalized == "openrouter":
        if not _openrouter_supports_native_web(provider.model_type):
            return None
        return {
            "plugins": [
                {
                    "id": "web",
                    "engine": "native",
                    "max_results": 3,
                }
            ]
        }
    if normalized in {"gemini", "google"}:
        return {"tools": [{"google_search": {}}]}
    if normalized == "openai":
        return {"tools": [{"type": "web_search"}], "tool_choice": "auto"}
    return None


def _openrouter_supports_native_web(model_type: str | None) -> bool:
    if not model_type:
        return False
    base = model_type.strip().lower().split(":", 1)[0]
    return base.startswith(
        (
            "openai/",
            "anthropic/",
            "perplexity/",
            "x-ai/",
            "xai/",
        )
    )


async def _is_complex_task(provider: ProviderConfig, question: str, context: str) -> tuple[bool, int]:
    prompt = build_complexity_prompt(question, context)
    messages = [
        {"role": "system", "content": "You are a classifier. Reply only \"yes\" or \"no\"."},
        {"role": "user", "content": prompt},
    ]
    text, usage = await collect_chat_completion(provider, messages, temperature=0.0)
    normalized = "".join(ch for ch in text.strip().lower() if ch.isalpha())
    if normalized.startswith("no"):
        return False, _usage_total(usage)
    if normalized.startswith("yes"):
        return True, _usage_total(usage)
    return True, _usage_total(usage)


def _strip_search_tools(tools: list[str], include_browser: bool) -> list[str]:
    blocked = {
        "search",
        "search_toolkit",
    }
    if include_browser:
        blocked.update(
            {
                "browser",
                "browser_toolkit",
                "hybrid_browser",
                "hybrid_browser_toolkit",
                "hybrid_browser_toolkit_py",
                "async_browser_toolkit",
            }
        )
    return [tool for tool in tools if tool not in blocked]


_SEARCH_INTENT_PATTERN = re.compile(
    r"\b(web\s+search|search the web|search online|search for|look up|lookup|google|bing|browse the web|find sources|latest news|recent news)\b",
    re.IGNORECASE,
)


def _detect_search_intent(question: str) -> bool:
    if not question:
        return False
    return bool(_SEARCH_INTENT_PATTERN.search(question))


def _detect_custom_runtime_skills(
    question: str,
    extension_set: set[str],
    custom_candidates: list[SkillEntry],
) -> list[RuntimeSkill]:
    if not custom_candidates:
        return []
    detected: list[RuntimeSkill] = []
    for catalog_skill in custom_candidates:
        if not catalog_skill.storage_path:
            continue
        skill_root = Path(catalog_skill.storage_path) / "contents"
        if not skill_root.exists():
            continue
        try:
            loaded = load_skill_packs(skill_root)
        except Exception:
            continue
        for skill in loaded.skills:
            if skill.matches_question(question) or skill.matches_extensions(extension_set):
                detected.append(skill)
    deduped: list[RuntimeSkill] = []
    seen_ids: set[str] = set()
    for skill in detected:
        if skill.id in seen_ids:
            continue
        seen_ids.add(skill.id)
        deduped.append(skill)
    return deduped


async def _extract_response(response) -> tuple[str, dict | None]:
    if isinstance(response, AsyncStreamingChatAgentResponse):
        content_parts: list[str] = []
        async for chunk in response:
            if chunk.msg and chunk.msg.content:
                content_parts.append(chunk.msg.content)
        final_response = await response
        usage = None
        if hasattr(final_response, "info"):
            usage = final_response.info.get("usage") or final_response.info.get("token_usage")
        return "".join(content_parts).strip(), usage
    content = ""
    if getattr(response, "msg", None):
        content = response.msg.content or ""
    usage = None
    if hasattr(response, "info"):
        usage = response.info.get("usage") or response.info.get("token_usage")
    return content.strip(), usage
