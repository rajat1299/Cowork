from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import re
from typing import Any, Iterable

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
    skill_root: str = ""
    policy_file: str = ""
    template_files: tuple[str, ...] = ()
    resource_files: tuple[str, ...] = ()
    policy_markdown: str = ""
    templates: dict[str, str] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)
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

    def has_policy_reference(self) -> bool:
        return bool(self.policy_file)

    def with_loaded_policy(self, errors: list[str] | None = None) -> RuntimeSkill:
        if self.policy_markdown or not self.policy_file:
            return self
        root = self._skill_root_path()
        if root is None:
            return self
        policy_path = root / self.policy_file
        if not policy_path.exists():
            return self
        try:
            policy_markdown = policy_path.read_text(encoding="utf-8")
        except OSError as exc:
            if errors is not None:
                errors.append(f"{policy_path}: {exc}")
            return self
        return replace(self, policy_markdown=policy_markdown)

    def with_loaded_templates(
        self,
        template_names: Iterable[str] | None = None,
        errors: list[str] | None = None,
    ) -> RuntimeSkill:
        if not self.template_files:
            return self
        root = self._skill_root_path()
        if root is None:
            return self
        requested = set(template_names or self.template_files)
        available = set(self.template_files)
        pending = sorted(name for name in requested if name in available and name not in self.templates)
        if not pending:
            return self

        templates_dir = root / "templates"
        templates = dict(self.templates)
        for template_name in pending:
            template_path = templates_dir / template_name
            try:
                templates[template_name] = template_path.read_text(encoding="utf-8")
            except OSError as exc:
                if errors is not None:
                    errors.append(f"{template_path}: {exc}")
        return replace(self, templates=templates)

    def with_loaded_resources(
        self,
        resource_names: Iterable[str] | None = None,
        errors: list[str] | None = None,
    ) -> RuntimeSkill:
        if not self.resource_files:
            return self
        root = self._skill_root_path()
        if root is None:
            return self
        requested = set(resource_names or self.resource_files)
        available = set(self.resource_files)
        pending = sorted(name for name in requested if name in available and name not in self.resources)
        if not pending:
            return self

        resources_dir = root / "resources"
        resources = dict(self.resources)
        for resource_name in pending:
            relative = Path(resource_name)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            resource_path = resources_dir / relative
            try:
                resources[resource_name] = resource_path.read_text(encoding="utf-8")
            except OSError as exc:
                if errors is not None:
                    errors.append(f"{resource_path}: {exc}")
        return replace(self, resources=resources)

    def _skill_root_path(self) -> Path | None:
        if not self.skill_root:
            return None
        return Path(self.skill_root)


@dataclass
class SkillPackLoadResult:
    skills: list[RuntimeSkill]
    errors: list[str]


def _scan_template_files(pack_dir: Path) -> tuple[str, ...]:
    templates_dir = pack_dir / "templates"
    if not templates_dir.exists() or not templates_dir.is_dir():
        return ()
    names: list[str] = []
    for template_file in sorted(templates_dir.glob("*.md")):
        if template_file.is_file():
            names.append(template_file.name)
    return tuple(names)


def _scan_resource_files(pack_dir: Path) -> tuple[str, ...]:
    resources_dir = pack_dir / "resources"
    if not resources_dir.exists() or not resources_dir.is_dir():
        return ()
    files: list[str] = []
    for resource_file in sorted(resources_dir.rglob("*")):
        if not resource_file.is_file():
            continue
        try:
            relative = resource_file.relative_to(resources_dir)
        except ValueError:
            continue
        files.append(str(relative).replace("\\", "/"))
    return tuple(files)


def load_skill_packs(
    skillpack_root: Path,
    *,
    load_policy: bool = False,
    load_templates: bool = False,
    load_resources: bool = False,
) -> SkillPackLoadResult:
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

        policy_file = "policy.md" if (pack_dir / "policy.md").exists() else ""
        template_files = _scan_template_files(pack_dir)
        resource_files = _scan_resource_files(pack_dir)

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
            skill_root=str(pack_dir),
            policy_file=policy_file,
            template_files=template_files,
            resource_files=resource_files,
        )
        if load_policy:
            skill = skill.with_loaded_policy(errors=errors)
        if load_templates:
            skill = skill.with_loaded_templates(errors=errors)
        if load_resources:
            skill = skill.with_loaded_resources(errors=errors)
        skills.append(skill)

    return SkillPackLoadResult(skills=skills, errors=errors)
