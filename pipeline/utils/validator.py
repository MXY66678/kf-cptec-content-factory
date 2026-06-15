"""Data validation utilities using Pydantic schemas."""

from __future__ import annotations

import json
from typing import Any, Optional, Type, TypeVar

from loguru import logger as log
from pydantic import BaseModel, ValidationError

from config import REQUIRED_KEYWORD_COVERAGE

T = TypeVar("T", bound=BaseModel)


def validate_schema(data: dict[str, Any], model_class: Type[T]) -> T:
    """Validate a dictionary against a Pydantic model.

    Args:
        data: Data to validate.
        model_class: Pydantic model class.

    Returns:
        Validated model instance.

    Raises:
        ValidationError: If data does not match schema.
    """
    try:
        return model_class(**data)
    except ValidationError as e:
        log.error("Schema validation failed for {}: {}", model_class.__name__, e)
        raise


def validate_json_string(json_str: str, model_class: Type[T]) -> T:
    """Parse JSON string and validate against a Pydantic model."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    try:
        return model_class(**data)
    except ValidationError as e:
        raise ValueError(f"Schema validation failed: {e}") from e


def check_keyword_coverage(
    seo_data: dict[str, Any],
    blog_sections: list[dict[str, Any]],
) -> tuple[bool, float, list[str]]:
    """Check that ≥90% of keyword clusters are mapped to blog sections.

    Args:
        seo_data: SEO keywords output with intent_clusters.
        blog_sections: Blog structure sections list.

    Returns:
        Tuple of (passed: bool, coverage_pct: float, unmapped_clusters: list[str]).
    """
    clusters = seo_data.get("intent_clusters", [])
    if not clusters:
        return True, 1.0, []

    # Collect all assigned keywords from sections
    section_keywords: set[str] = set()
    for sec in blog_sections:
        for kw in sec.get("assigned_keywords", []):
            section_keywords.add(kw.lower().strip())

    mapped_count = 0
    unmapped_clusters: list[str] = []

    for cluster in clusters:
        primary = cluster.get("primary", "").lower().strip()
        cluster_kws = [k.lower().strip() for k in cluster.get("keywords", [])]
        # Check if primary or any keyword appears in section keywords
        is_mapped = primary in section_keywords or any(
            kw in section_keywords for kw in cluster_kws
        )
        if is_mapped:
            mapped_count += 1
        else:
            unmapped_clusters.append(cluster.get("cluster_name", cluster.get("primary", "unknown")))

    total = len(clusters)
    coverage = mapped_count / total if total > 0 else 1.0
    passed = coverage >= REQUIRED_KEYWORD_COVERAGE
    return passed, coverage, unmapped_clusters


def validate_step_intents(
    sections: list[dict[str, Any]],
    vocabulary: list[str],
) -> tuple[bool, list[str]]:
    """Validate that all how_to_step sections have valid step_intent.

    Returns:
        Tuple of (passed: bool, errors: list[str]).
    """
    errors: list[str] = []
    for i, sec in enumerate(sections):
        st = sec.get("step_intent")
        if sec.get("section_type") == "how_to_step":
            if not st or st == "null":
                errors.append(f"Section {i} ('{sec.get('heading_text', '')}') "
                              f"is how_to_step but missing step_intent")
            elif st not in vocabulary:
                errors.append(f"Section {i}: step_intent '{st}' not in vocabulary {vocabulary}")
    return len(errors) == 0, errors


def validate_field_lengths(
    sections: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Enforce field length limits on blog structure fields."""
    errors: list[str] = []
    for i, sec in enumerate(sections):
        heading = sec.get("heading_text", "")
        if len(heading) > 200:
            errors.append(f"Section {i}: heading_text exceeds 200 chars ({len(heading)})")
        brief = sec.get("content_brief", "")
        words = len(brief.split())
        if words > 40:
            errors.append(f"Section {i}: content_brief exceeds 40 words ({words})")
        video = sec.get("video_slot")
        if video is not None and video != "" and video != "null":
            pass  # valid video ID or actual null
    return len(errors) == 0, errors


def validate_assembly(
    master: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Full assembly validation: schema, keyword coverage, intents, field lengths.

    Returns:
        Tuple of (passed: bool, errors: list[str]).
    """
    errors: list[str] = []

    # 1. Check required keys
    for key in ["sku_id", "blog_structure", "seo_keywords", "video_links", "amazon_listing_blocks"]:
        if key not in master:
            errors.append(f"Missing required key: {key}")

    if errors:
        return False, errors

    blog = master["blog_structure"]
    sections = blog.get("sections", [])
    seo = master["seo_keywords"]

    # 2. Keyword coverage
    coverage_ok, coverage_pct, unmapped = check_keyword_coverage(seo, sections)
    if not coverage_ok:
        errors.append(
            f"Keyword coverage {coverage_pct:.1%} < {REQUIRED_KEYWORD_COVERAGE:.0%}. "
            f"Unmapped: {unmapped}"
        )

    # 3. Step intents
    vocabulary = blog.get("step_intent_vocabulary", [])
    intents_ok, intent_errors = validate_step_intents(sections, vocabulary)
    if not intents_ok:
        errors.extend(intent_errors)

    # 4. Field lengths
    lengths_ok, length_errors = validate_field_lengths(sections)
    if not lengths_ok:
        errors.extend(length_errors)

    # 5. All how_to_step sections must have video_slot key (can be null)
    for i, sec in enumerate(sections):
        if sec.get("section_type") == "how_to_step" and "video_slot" not in sec:
            errors.append(f"Section {i}: how_to_step missing video_slot key")

    return len(errors) == 0, errors
