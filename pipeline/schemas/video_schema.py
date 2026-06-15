"""Video links schema — Pydantic models for M4 (YouTube) output."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VideoLink(BaseModel):
    """A single matched YouTube video."""
    video_id: str = Field(..., max_length=50)
    url: str = Field(..., max_length=200)
    channel: str = Field(..., max_length=100)
    matched_step: str = Field(..., description="Heading text of the matched section")
    match_score: float = Field(..., ge=0.0, le=1.0)
    embed_html: Optional[str] = Field(None, max_length=500)
    health_checked_at: Optional[str] = Field(None, description="ISO-8601 timestamp")


class VideoSlotMapping(BaseModel):
    """A single video slot assignment in the blog."""
    section_heading: str
    step_intent: str
    video: Optional[VideoLink] = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    fallback_chain_used: list[str] = Field(default_factory=list)
    slot_filled: bool = Field(default=False)


class VideoLinks(BaseModel):
    """Complete video retrieval output from M4 (YouTube)."""
    mappings: list[VideoSlotMapping] = Field(default_factory=list)
    total_slots: int = Field(default=0, ge=0)
    filled_slots: int = Field(default=0, ge=0)

    model_config = {"extra": "ignore"}
