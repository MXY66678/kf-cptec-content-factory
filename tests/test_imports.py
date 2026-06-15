"""Verify all pipeline imports work correctly."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_imports():
    """Test that all config values are importable."""
    import config
    assert config.PROJECT_ROOT.exists()
    assert config.PIPELINE_DIR.exists()
    assert config.VALID_STATES
    assert "PENDING" in config.VALID_STATES
    assert "FAILED" in config.VALID_STATES


def test_schema_imports():
    """Test that all pydantic schemas are importable and valid."""
    from pipeline.schemas.sku_schema import SKUCanonical, SKUSpec
    from pipeline.schemas.blog_schema import BlogStructure, Section
    from pipeline.schemas.seo_schema import SEOKeywords, IntentCluster
    from pipeline.schemas.video_schema import VideoLinks, VideoLink

    # Verify SKUCanonical validation
    sku = SKUCanonical(
        sku_id="KF-CPTEC-TEST-001",
        product_name="Test Product",
        category="crimp",
        tool_type="Test Tool",
    )
    assert sku.sku_id == "KF-CPTEC-TEST-001"
    assert sku.brand == "KF CPTEC"

    # Verify Section validation
    section = Section(
        heading_level="h2",
        heading_text="Test Section",
        section_type="intro",
        content_brief="Test brief for validation purposes.",
    )
    assert section.heading_level == "h2"

    print("Schema tests passed!")


def test_validators():
    """Test assembly validation functions."""
    from pipeline.utils.validator import (
        check_keyword_coverage,
        validate_step_intents,
        validate_field_lengths,
    )

    # Keyword coverage test
    seo = {
        "intent_clusters": [
            {
                "cluster_name": "test_cluster",
                "intent": "informational",
                "primary": "test keyword",
                "keywords": ["test keyword", "related term"],
                "long_tail": [],
                "merge_candidate": False,
                "mapped_section_type": "intro",
            }
        ]
    }
    sections = [
        {
            "heading_level": "h2",
            "heading_text": "Test Section",
            "section_type": "how_to_step",
            "step_intent": "overview",
            "assigned_keywords": ["test keyword"],
            "content_brief": "Test brief for verification.",
            "target_word_count": 100,
            "video_slot": None,
            "image_slot": None,
        }
    ]

    passed, coverage, unmapped = check_keyword_coverage(seo, sections)
    assert passed
    assert coverage >= 1.0
    assert len(unmapped) == 0

    # Step intent test
    vocab = ["overview", "prep", "position", "crimp", "inspect", "troubleshoot"]
    intents_ok, intent_errors = validate_step_intents(sections, vocab)
    assert intents_ok
    assert len(intent_errors) == 0

    # Field length test
    lengths_ok, length_errors = validate_field_lengths(sections)
    assert lengths_ok
    assert len(length_errors) == 0

    print("Validator tests passed!")


def test_state_machine():
    """Test the SKU state machine transitions."""
    from pipeline.core.state_machine import SKUStateMachine

    sm = SKUStateMachine("KF-CPTEC-TEST-001")
    assert sm.state == "PENDING"
    assert not sm.is_terminal
    assert not sm.is_failed

    sm.transition_to("M1")
    assert sm.state == "M1"

    sm.transition_to("M2")
    assert sm.state == "M2"

    sm.fail()
    assert sm.state == "FAILED"
    assert sm.is_terminal
    assert sm.is_failed

    print("State machine tests passed!")


def test_category_templates():
    """Test YAML category template loading."""
    import config
    from config import list_categories, get_category_template

    categories = list_categories()
    assert "crimp" in categories
    assert "press" in categories
    assert "cutter" in categories

    template = get_category_template("crimp")
    assert template.get("category") == "crimp"
    assert "step_intent_vocabulary" in template
    assert "overview" in template["step_intent_vocabulary"]

    print("Category template tests passed!")


def test_sample_data():
    """Test sample data generation functions."""
    from main import generate_sample_data, generate_mock_master

    manifest, keyword_csv, specs = generate_sample_data()
    assert len(manifest) == 2
    assert len(keyword_csv) > 0
    assert "crimp-001" in specs

    master = generate_mock_master(manifest[0]["sku_id"], manifest[0])
    assert master["sku_id"] == manifest[0]["sku_id"]
    assert master["state"] == "ASSEMBLED"
    assert len(master["blog_structure"]["sections"]) == 12

    # Validate keyword coverage
    seo = master["seo_keywords"]
    blog = master["blog_structure"]
    from pipeline.utils.validator import check_keyword_coverage
    passed, coverage, _ = check_keyword_coverage(seo, blog["sections"])
    assert passed
    assert coverage >= 0.9

    print("Sample data tests passed!")


if __name__ == "__main__":
    test_config_imports()
    test_schema_imports() 
    test_validators()
    test_state_machine()
    test_category_templates()
    test_sample_data()
    print("\nAll tests passed!")
