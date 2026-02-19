from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillCatalogEntry:
    skill_id: str
    name: str
    description: str
    source: str
    domains: tuple[str, ...] = ()
    trigger_keywords: tuple[str, ...] = ()
    trigger_extensions: tuple[str, ...] = ()
    enabled_by_default: bool = False


BUILT_IN_SKILLS: tuple[SkillCatalogEntry, ...] = (
    SkillCatalogEntry(
        skill_id="doc_docx_v1",
        name="docx",
        description="Word document creation and conversion workload.",
        source="built_in",
        domains=("docs", "office"),
        trigger_keywords=("docx", "word document", "word"),
        trigger_extensions=(".docx",),
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_markdown_v1",
        name="doc_markdown",
        description="Markdown document authoring with structural checks.",
        source="built_in",
        domains=("docs", "markdown"),
        trigger_keywords=("markdown", "readme", "documentation"),
        trigger_extensions=(".md", ".txt"),
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_pdf_v1",
        name="pdf",
        description="PDF creation and extraction workload.",
        source="built_in",
        domains=("docs", "pdf"),
        trigger_keywords=("pdf", "portable document"),
        trigger_extensions=(".pdf",),
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="doc_revision_v1",
        name="doc_revision",
        description="Revision of existing files with style preserved.",
        source="built_in",
        domains=("docs",),
        trigger_keywords=("revise", "rewrite", "edit document"),
        trigger_extensions=(".docx", ".md", ".pdf", ".txt"),
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="research_web_v1",
        name="research_web",
        description="Research and web browsing with source checks.",
        source="built_in",
        domains=("research", "web"),
        trigger_keywords=("research", "sources", "web search", "browse"),
        enabled_by_default=True,
    ),
    SkillCatalogEntry(
        skill_id="spreadsheet_v1",
        name="xlsx",
        description="Spreadsheet creation with formula expectations.",
        source="built_in",
        domains=("spreadsheet", "office"),
        trigger_keywords=("spreadsheet", "xlsx", "excel", "formula"),
        trigger_extensions=(".xlsx", ".csv"),
        enabled_by_default=True,
    ),
)


EXAMPLE_SKILLS: tuple[SkillCatalogEntry, ...] = (
    SkillCatalogEntry(
        skill_id="algorithmic_art",
        name="algorithmic-art",
        description="Creating algorithmic art using p5.js with seeded randomness and interactive exploration.",
        source="example",
        domains=("art", "generative"),
        trigger_keywords=("algorithmic art", "generative art", "p5.js", "flow field", "particle"),
        trigger_extensions=(".js",),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="brand_guidelines",
        name="brand-guidelines",
        description="Apply Anthropic brand colors and typography to generated artifacts.",
        source="example",
        domains=("design", "brand"),
        trigger_keywords=("brand guideline", "brand colors", "typography", "style guide"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="canvas_design",
        name="canvas-design",
        description="Create visual art in PNG/PDF documents using design philosophy workflows.",
        source="example",
        domains=("design", "art"),
        trigger_keywords=("canvas design", "poster", "visual design", "png", "pdf design"),
        trigger_extensions=(".png", ".pdf"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="doc_coauthoring",
        name="doc-coauthoring",
        description="Structured workflow for co-authoring documentation and technical specs.",
        source="example",
        domains=("docs",),
        trigger_keywords=("coauthor", "technical spec", "proposal", "documentation"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="internal_comms",
        name="internal-comms",
        description="Templates and guidance for internal communications and project updates.",
        source="example",
        domains=("communications",),
        trigger_keywords=("status report", "leadership update", "newsletter", "incident report"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="mcp_builder",
        name="mcp-builder",
        description="Guidance for building MCP servers that integrate external services.",
        source="example",
        domains=("engineering", "mcp"),
        trigger_keywords=("mcp server", "model context protocol", "fastmcp", "mcp sdk"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="skill_creator",
        name="skill-creator",
        description="Create and improve skills with structured authoring workflows.",
        source="example",
        domains=("engineering", "skills"),
        trigger_keywords=("create skill", "skill authoring", "skill benchmark"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="slack_gif_creator",
        name="slack-gif-creator",
        description="Create animated GIFs optimized for Slack constraints.",
        source="example",
        domains=("media", "communications"),
        trigger_keywords=("gif", "animated gif", "slack gif"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="theme_factory",
        name="theme-factory",
        description="Apply visual themes to artifacts such as slides and docs.",
        source="example",
        domains=("design",),
        trigger_keywords=("theme", "styling", "visual theme"),
        enabled_by_default=False,
    ),
    SkillCatalogEntry(
        skill_id="web_artifacts_builder",
        name="web-artifacts-builder",
        description="Build multi-component HTML artifacts using modern frontend patterns.",
        source="example",
        domains=("web", "engineering"),
        trigger_keywords=("web artifact", "html artifact", "react artifact", "tailwind"),
        trigger_extensions=(".html", ".tsx", ".jsx"),
        enabled_by_default=False,
    ),
)


DEFAULT_SKILL_CATALOG: tuple[SkillCatalogEntry, ...] = BUILT_IN_SKILLS + EXAMPLE_SKILLS
