"""SEO keywords schema — Pydantic models for keyword clustering output."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class IntentCluster(BaseModel):
    """A single intent keyword cluster."""
    cluster_name: str = Field(..., max_length=100)
    intent: str = Field(..., pattern=r"^(informational|transactional|comparison|navigational)$")
    primary: str = Field(..., max_length=100)
    keywords: list[str] = Field(..., min_length=1)
    long_tail: list[str] = Field(default_factory=list)
    merge_candidate: bool = Field(default=False)
    mapped_section_type: Optional[str] = Field(
        None,
        description="Section type this cluster maps to",
    )


class DensityTargets(BaseModel):
    """Keyword density targets for content."""
    primary: str = Field(default="1-2%")
    secondary: str = Field(default="0.5-1%")


class SEOKeywords(BaseModel):
    """Complete SEO keywords output from M1 (DeepSeek)."""
    intent_clusters: list[IntentCluster] = Field(..., min_length=1)
    density_targets: DensityTargets = Field(default_factory=DensityTargets)
    excluded_navigational: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class SEOKeywordsExpanded(SEOKeywords):
    """SEO keywords with mapped section references filled by assembly."""
    pass
