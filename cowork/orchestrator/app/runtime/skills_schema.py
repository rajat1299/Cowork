from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from pydantic import BaseModel, Field, ValidationError


class SkillTriggerConfig(BaseModel):
    regex: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)


class SkillOutputContractConfig(BaseModel):
    required_artifact: bool = False
    allowed_extensions: list[str] = Field(default_factory=list)
    minimum_artifacts: int = 0
    description: str = ""


class SkillValidationConfig(BaseModel):
    rules: list[str] = Field(default_factory=list)


class SkillRetryPolicyConfig(BaseModel):
    max_attempts: int = 1
    strategies: list[str] = Field(default_factory=list)


class SkillPackConfig(BaseModel):
    id: str
    name: str
    version: str
    description: str = ""
    domains: list[str] = Field(default_factory=list)
    force_complex: bool = False
    required_tools: list[str] = Field(default_factory=list)
    prompt_instructions: list[str] = Field(default_factory=list)
    triggers: SkillTriggerConfig = Field(default_factory=SkillTriggerConfig)
    output_contract: SkillOutputContractConfig = Field(default_factory=SkillOutputContractConfig)
    validation_rules: SkillValidationConfig = Field(default_factory=SkillValidationConfig)
    retry_policy: SkillRetryPolicyConfig = Field(default_factory=SkillRetryPolicyConfig)


@dataclass(frozen=True)
class RuntimeSkill:
    id: str
    name: str
    version: str
    description: str = ""
    domains: tuple[str, ...] = ()
    trigger_patterns: tuple[str, ...] = ()
    file_extensions: tuple[str, ...] = ()
    force_complex: bool = False
    prompt_instructions: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    output_contract: SkillOutputContractConfig = field(default_factory=SkillOutputContractConfig)
    validation_rules: tuple[str, ...] = ()
    retry_policy: SkillRetryPolicyConfig = field(default_factory=SkillRetryPolicyConfig)
    policy_markdown: str = ""
    templates: dict[str, str] = field(default_factory=dict)
    _compiled_patterns: tuple[re.Pattern[str], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        compiled: list[re.Pattern[str]] = []
        for pattern in self.trigger_patterns:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                continue
        object.__setattr__(self, "_compiled_patterns", tuple(compiled))

    def matches_question(self, question: str) -> bool:
        if not question:
            return False
        return any(pattern.search(question) for pattern in self._compiled_patterns)

    def matches_extensions(self, extensions: set[str]) -> bool:
        normalized_extensions = {ext.lower() for ext in extensions if ext}
        return any(ext.lower() in normalized_extensions for ext in self.file_extensions)


@dataclass
class SkillPackLoadResult:
    skills: list[RuntimeSkill]
    errors: list[str]


def load_skill_packs(skillpack_root: Path) -> SkillPackLoadResult:
    skills: list[RuntimeSkill] = []
    errors: list[str] = []
    if not skillpack_root.exists():
        return SkillPackLoadResult(skills=[], errors=[])

    for toml_path in sorted(skillpack_root.glob("*/skill.toml")):
        pack_dir = toml_path.parent
        try:
            with toml_path.open("rb") as file_obj:
                payload: dict[str, Any] = tomllib.load(file_obj)
            config = SkillPackConfig.model_validate(payload)
        except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
            errors.append(f"{toml_path}: {exc}")
            continue

        policy_path = pack_dir / "policy.md"
        policy_markdown = ""
        if policy_path.exists():
            try:
                policy_markdown = policy_path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"{policy_path}: {exc}")

        templates: dict[str, str] = {}
        templates_dir = pack_dir / "templates"
        if templates_dir.exists() and templates_dir.is_dir():
            for template_file in sorted(templates_dir.glob("*.md")):
                try:
                    templates[template_file.name] = template_file.read_text(encoding="utf-8")
                except OSError as exc:
                    errors.append(f"{template_file}: {exc}")

        skill = RuntimeSkill(
            id=config.id,
            name=config.name,
            version=config.version,
            description=config.description,
            domains=tuple(config.domains),
            trigger_patterns=tuple(config.triggers.regex),
            file_extensions=tuple(ext.lower() for ext in config.triggers.extensions),
            force_complex=config.force_complex,
            prompt_instructions=tuple(config.prompt_instructions),
            required_tools=tuple(config.required_tools),
            output_contract=config.output_contract,
            validation_rules=tuple(config.validation_rules.rules),
            retry_policy=config.retry_policy,
            policy_markdown=policy_markdown,
            templates=templates,
        )
        skills.append(skill)

    return SkillPackLoadResult(skills=skills, errors=errors)
