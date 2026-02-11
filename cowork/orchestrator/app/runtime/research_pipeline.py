from __future__ import annotations

import re
from typing import Any


def expand_queries(question: str) -> list[str]:
    normalized = (question or "").strip()
    if not normalized:
        return []

    candidates = [normalized]
    if "paper" in normalized.lower():
        candidates.append(f"{normalized} abstract methodology key findings")
    if "latest" not in normalized.lower():
        candidates.append(f"{normalized} latest updates")
    if "benchmark" not in normalized.lower():
        candidates.append(f"{normalized} benchmarks and results")

    deduped: list[str] = []
    seen = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def dedupe_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen = set()
    for row in results:
        url = str(row.get("url") or "").strip().lower()
        title = str(row.get("title") or row.get("text") or "").strip().lower()
        key = url or title
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def extract_citations(text: str) -> list[str]:
    if not text:
        return []
    urls = re.findall(r"https?://[^\s\])>\"']+", text)
    bracketed = re.findall(r"\[Source:\s*([^\]]+)\]", text, re.IGNORECASE)
    combined = urls + bracketed
    deduped: list[str] = []
    seen = set()
    for item in combined:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def should_retry_search(result_payload: Any) -> bool:
    if isinstance(result_payload, dict):
        if result_payload.get("error"):
            return True
        if isinstance(result_payload.get("results"), list):
            return len(result_payload["results"]) == 0
    return False
