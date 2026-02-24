from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


_MAX_ARCHIVE_MEMBERS = 400
_MAX_MEMBER_BYTES = 2 * 1024 * 1024
_MAX_TOTAL_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
_MAX_SCAN_BYTES = 200_000

_BLOCKED_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".class",
    ".jar",
}
_SUSPECT_BINARY_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz"}

_BLOCK_PATTERNS = (
    ("shell_pipe_exec", re.compile(r"(curl|wget)[^\n]{0,160}\|\s*(sh|bash|zsh)\b", re.IGNORECASE)),
    ("rm_root", re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.IGNORECASE)),
    ("reverse_shell", re.compile(r"\bnc\b[^\n]{0,160}\s-e\s", re.IGNORECASE)),
)
_WARNING_PATTERNS = (
    ("external_http", re.compile(r"https?://", re.IGNORECASE)),
    ("requests_post", re.compile(r"\brequests\.(post|put|patch)\b", re.IGNORECASE)),
    ("httpx_post", re.compile(r"\bhttpx\.(post|put|patch)\b", re.IGNORECASE)),
    ("subprocess_shell", re.compile(r"\bsubprocess\.(run|Popen)\s*\([^)]*shell\s*=\s*True", re.IGNORECASE)),
)


@dataclass(frozen=True)
class SkillSecurityIssue:
    severity: str
    code: str
    file_path: str
    message: str


@dataclass(frozen=True)
class SkillSecurityReport:
    trust_state: str
    scan_status: str
    warnings: list[str]
    blocked_issue: SkillSecurityIssue | None = None

    @property
    def is_blocked(self) -> bool:
        return self.blocked_issue is not None


def analyze_skill_zip(zip_path: Path) -> SkillSecurityReport:
    issues: list[SkillSecurityIssue] = []
    total_uncompressed_bytes = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) > _MAX_ARCHIVE_MEMBERS:
                return _blocked(
                    code="too_many_files",
                    file_path="(archive)",
                    message=f"Archive has too many files ({len(members)} > {_MAX_ARCHIVE_MEMBERS}).",
                )
            for member in members:
                file_path = member.filename
                if file_path.startswith("__MACOSX/"):
                    continue
                path_obj = Path(file_path)
                if path_obj.is_absolute() or ".." in path_obj.parts:
                    return _blocked(
                        code="unsafe_path",
                        file_path=file_path,
                        message="Archive contains unsafe file paths.",
                    )
                total_uncompressed_bytes += int(member.file_size or 0)
                if member.file_size > _MAX_MEMBER_BYTES:
                    return _blocked(
                        code="member_too_large",
                        file_path=file_path,
                        message=f"File exceeds max allowed size ({_MAX_MEMBER_BYTES} bytes).",
                    )
                if total_uncompressed_bytes > _MAX_TOTAL_UNCOMPRESSED_BYTES:
                    return _blocked(
                        code="archive_too_large_uncompressed",
                        file_path="(archive)",
                        message="Archive exceeds total uncompressed size limit.",
                    )

                ext = path_obj.suffix.lower()
                if ext in _BLOCKED_EXTENSIONS:
                    return _blocked(
                        code="blocked_extension",
                        file_path=file_path,
                        message=f"File extension '{ext}' is not allowed for uploaded skills.",
                    )

                try:
                    content = archive.read(member)
                except Exception:
                    continue
                if not content:
                    continue
                if ext in _SUSPECT_BINARY_EXTENSIONS and b"\x00" in content[:2048]:
                    issues.append(
                        SkillSecurityIssue(
                            severity="warning",
                            code="binary_payload",
                            file_path=file_path,
                            message="Binary payload detected in skill archive.",
                        )
                    )
                    continue
                text = _decode_for_scan(content)
                if text is None:
                    continue
                if len(text) > _MAX_SCAN_BYTES:
                    text = text[:_MAX_SCAN_BYTES]
                blocked_issue = _scan_block_patterns(text, file_path)
                if blocked_issue is not None:
                    return _blocked_issue(blocked_issue)
                issues.extend(_scan_warning_patterns(text, file_path))
    except zipfile.BadZipFile:
        return _blocked(
            code="invalid_zip",
            file_path="(archive)",
            message="Invalid zip archive.",
        )

    warnings = _dedupe_warning_messages(issues)
    if warnings:
        return SkillSecurityReport(
            trust_state="review_required",
            scan_status="warning",
            warnings=warnings,
        )
    return SkillSecurityReport(
        trust_state="trusted",
        scan_status="passed",
        warnings=[],
    )


def _decode_for_scan(content: bytes) -> str | None:
    if b"\x00" in content[:4096]:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="ignore")


def _scan_block_patterns(text: str, file_path: str) -> SkillSecurityIssue | None:
    for code, pattern in _BLOCK_PATTERNS:
        if pattern.search(text):
            return SkillSecurityIssue(
                severity="block",
                code=code,
                file_path=file_path,
                message=f"Blocked by security policy ({code}).",
            )
    return None


def _scan_warning_patterns(text: str, file_path: str) -> list[SkillSecurityIssue]:
    warnings: list[SkillSecurityIssue] = []
    for code, pattern in _WARNING_PATTERNS:
        if pattern.search(text):
            warnings.append(
                SkillSecurityIssue(
                    severity="warning",
                    code=code,
                    file_path=file_path,
                    message=f"Potentially risky pattern detected ({code}).",
                )
            )
    return warnings


def _dedupe_warning_messages(issues: list[SkillSecurityIssue]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        msg = f"{issue.file_path}: {issue.message}"
        if msg in seen:
            continue
        seen.add(msg)
        deduped.append(msg)
    return deduped


def _blocked(code: str, file_path: str, message: str) -> SkillSecurityReport:
    return _blocked_issue(
        SkillSecurityIssue(
            severity="block",
            code=code,
            file_path=file_path,
            message=message,
        )
    )


def _blocked_issue(issue: SkillSecurityIssue) -> SkillSecurityReport:
    return SkillSecurityReport(
        trust_state="blocked",
        scan_status="failed",
        warnings=[],
        blocked_issue=issue,
    )
