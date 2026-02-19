from app.skills_catalog import DEFAULT_SKILL_CATALOG, EXAMPLE_SKILLS


def test_example_skills_are_marked_example_source():
    assert EXAMPLE_SKILLS
    assert all(entry.source == "example" for entry in EXAMPLE_SKILLS)


def test_catalog_entries_include_discovery_metadata_shapes():
    assert DEFAULT_SKILL_CATALOG
    for entry in DEFAULT_SKILL_CATALOG:
        assert isinstance(entry.domains, tuple)
        assert isinstance(entry.trigger_keywords, tuple)
        assert isinstance(entry.trigger_extensions, tuple)
