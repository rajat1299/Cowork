from __future__ import annotations

from pathlib import Path
import re


_STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "for",
    "of",
    "on",
    "in",
    "with",
    "from",
    "by",
}


def extract_explicit_filenames(question: str) -> set[str]:
    if not question:
        return set()
    candidates = set()
    for match in re.finditer(r"([A-Za-z0-9 _.-]+\.[A-Za-z0-9]{1,8})", question):
        filename = match.group(1).strip().strip('"`')
        if "/" in filename or "\\" in filename:
            filename = Path(filename).name
        if filename:
            candidates.add(filename)
    return candidates


def is_machine_style_filename(filename: str) -> bool:
    stem = Path(filename).stem
    if not stem:
        return False
    return "_" in stem or bool(re.search(r"[a-z][A-Z]", stem))


def humanize_filename(filename: str) -> str:
    path = Path(filename)
    stem = path.stem
    extension = path.suffix
    if not stem:
        return filename

    normalized = stem.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        normalized = "Output"

    words = []
    for token in normalized.split(" "):
        if token.isupper() and len(token) <= 5:
            words.append(token)
        elif token.lower() in {"ai", "ml", "nlp", "rag", "pdf", "docx"}:
            words.append(token.upper())
        else:
            words.append(token.capitalize())
    title = " ".join(words)
    return f"{title}{extension}"


def suggest_filename(question: str, extension: str, fallback_stem: str = "Output") -> str:
    if not extension.startswith("."):
        extension = f".{extension}"

    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", question or "")
        if token.lower() not in _STOPWORDS
    ]
    stem_tokens = tokens[:6]
    if not stem_tokens:
        stem_tokens = [fallback_stem]
    stem = " ".join(token.upper() if token.lower() in {"ai", "rag", "nlp"} else token.capitalize() for token in stem_tokens)
    return f"{stem}{extension}"


def normalize_filename_for_output(filename: str, explicit_names: set[str]) -> str:
    if not filename:
        return filename
    name_only = Path(filename).name
    if name_only in explicit_names:
        return name_only
    if not is_machine_style_filename(name_only):
        return name_only
    return humanize_filename(name_only)
