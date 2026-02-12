from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillCatalogEntry:
    skill_id: str
    name: str
    description: str
    source: str
    enabled_by_default: bool = False


BUILT_IN_SKILLS: tuple[SkillCatalogEntry, ...] = (
    SkillCatalogEntry(
        skill_id="doc_docx_v1",
        name="docx",
        description="Word document creation and conversion workload.",
        source="built_in",
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_markdown_v1",
        name="doc_markdown",
        description="Markdown document authoring with structural checks.",
        source="built_in",
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_pdf_v1",
        name="pdf",
        description="PDF creation and extraction workload.",
        source="built_in",
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_revision_v1",
        name="doc_revision",
        description="Revision of existing files with style preserved.",
        source="built_in",
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="research_web_v1",
        name="research_web",
        description="Research and web browsing with source checks.",
        source="built_in",
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="spreadsheet_v1",
        name="xlsx",
        description="Spreadsheet creation with formula expectations.",
        source="built_in",
        enabled_by_default=True,
    ),
)


EXAMPLE_SKILLS: tuple[SkillCatalogEntry, ...] = (
    SkillCatalogEntry(
        skill_id="algorithmic_art",
        name="algorithmic-art",
        description="Creating algorithmic art using p5.js with seeded randomness and interactive exploration.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="brand_guidelines",
        name="brand-guidelines",
        description="Apply Anthropic brand colors and typography to generated artifacts.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="canvas_design",
        name="canvas-design",
        description="Create visual art in PNG/PDF documents using design philosophy workflows.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="doc_coauthoring",
        name="doc-coauthoring",
        description="Structured workflow for co-authoring documentation and technical specs.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="internal_comms",
        name="internal-comms",
        description="Templates and guidance for internal communications and project updates.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="mcp_builder",
        name="mcp-builder",
        description="Guidance for building MCP servers that integrate external services.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="skill_creator",
        name="skill-creator",
        description="Create and improve skills with structured authoring workflows.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="slack_gif_creator",
        name="slack-gif-creator",
        description="Create animated GIFs optimized for Slack constraints.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="theme_factory",
        name="theme-factory",
        description="Apply visual themes to artifacts such as slides and docs.",
        source="example",
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="web_artifacts_builder",
        name="web-artifacts-builder",
        description="Build multi-component HTML artifacts using modern frontend patterns.",
        source="example",
        enabled_by_default=False,
    ),
)


DEFAULT_SKILL_CATALOG: tuple[SkillCatalogEntry, ...] = BUILT_IN_SKILLS + EXAMPLE_SKILLS
