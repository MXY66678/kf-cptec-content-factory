"""Blog structure schema — Pydantic models for M3 (Claude) output."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Section(BaseModel):
    """A single section in the blog structure."""
    heading_level: str = Field(..., pattern=r"^(h2|h3)$")
    heading_text: str = Field(..., max_length=200)
    section_type: str = Field(
        ...,
        pattern=r"^(intro|tool_overview|how_to_step|comparison|faq|cta)$",
    )
    step_intent: Optional[str] = Field(
        None,
        pattern=r"^(overview|prep|position|crimp|inspect|troubleshoot|null|)$",
    )
    content_brief: str = Field(..., max_length=500)
    target_word_count: int = Field(default=150, ge=0, le=2000)
    assigned_keywords: list[str] = Field(default_factory=list)
    video_slot: Optional[str] = Field(
        None,
        description="YouTube video ID or null",
    )
    image_slot: Optional[str] = Field(
        None,
        description="Image block ID reference or null",
    )


class BlogStructure(BaseModel):
    """Complete blog structure output from M3 (Claude)."""
    title: str = Field(..., max_length=200)
    meta_description: str = Field(..., max_length=155)
    url_slug: str = Field(..., max_length=100)
    schema_markup: list[str] = Field(
        default_factory=lambda: ["HowTo", "FAQPage", "Product"],
    )
    sections: list[Section] = Field(..., min_length=1)
    internal_links: list[str] = Field(default_factory=list)
    step_intent_vocabulary: list[str] = Field(
        default_factory=lambda: ["overview", "prep", "position", "crimp", "inspect", "troubleshoot"],
    )

    model_config = {"extra": "ignore"}
