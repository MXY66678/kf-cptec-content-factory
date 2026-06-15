"""M3 — Claude SEO Blog Architect Module.

Produces blog_structure ONLY (headings + section briefs).
NEVER generates full blog content.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger as log

from config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, CLAUDE_MODEL
from pipeline.schemas.blog_schema import BlogStructure
from pipeline.utils.http_client import APIClient
from pipeline.utils.retry import extract_json_from_text, retry_with_json_fallback


SYSTEM_PROMPT = """You are an SEO blog architect for technical plumbing tool content.
You produce STRUCTURE ONLY — heading trees, section briefs, tags.
Never write article prose. Never write marketing copy.
Output valid JSON matching the blog_structure schema. No other text.

Follow the structural pattern:
h1 -> h2(problem) -> h2(overview+spec table) -> h2(how-to) -> h3(steps x4-6) -> h2(troubleshoot) -> h2(comparison) -> h2(faq) -> h2(cta)

Follow the structural pattern. Do not copy any headings verbatim.

REQUIREMENTS:
1. H1 title: front-load primary keyword from the highest-volume transactional-informational hybrid cluster.
2. Every how_to_step section MUST carry:
   - step_intent from vocabulary: [overview, prep, position, crimp, inspect, troubleshoot]
   - assigned_keywords: 1 primary + 1-2 LSI from mapped cluster
   - video_slot: null (placeholder, filled by M4)
3. Map each keyword cluster to exactly one section (cluster.mapped_sections must be exhaustive, no orphan clusters).
4. content_brief = writer instructions (constraints, data points to include, callout boxes), max 40 words, imperative voice.
5. Include internal_links array.
6. Set schema_markup per section_type (how_to_step->HowTo, faq->FAQPage, tool_overview->Product).

OUTPUT JSON FORMAT:
{
  "title": "string (H1, primary keyword front-loaded)",
  "meta_description": "string (<=155 chars)",
  "url_slug": "string",
  "schema_markup": ["HowTo", "FAQPage", "Product"],
  "sections": [
    {
      "heading_level": "h2|h3",
      "heading_text": "string",
      "section_type": "intro|tool_overview|how_to_step|comparison|faq|cta",
      "step_intent": "overview|prep|position|crimp|inspect|troubleshoot|null",
      "content_brief": "string (writer instructions, max 40 words)",
      "target_word_count": 150,
      "assigned_keywords": ["string"],
      "video_slot": null,
      "image_slot": "image_block_id|null"
    }
  ],
  "internal_links": ["url"],
  "step_intent_vocabulary": ["overview", "prep", "position", "crimp", "inspect", "troubleshoot"],
  "video_slot_rules": {
    "max_per_section": 1,
    "source": "existing_youtube_only",
    "fill_policy": "leave_null_if_match_score_below_threshold"
  }
}"""


class ClaudeModule:
    """M3 SEO Blog Architect using Anthropic Claude API."""

    def __init__(self) -> None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = APIClient(
            base_url=ANTHROPIC_BASE_URL,
            api_key=ANTHROPIC_API_KEY,
            timeout=300.0,
            headers={
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        self.model = CLAUDE_MODEL

    def build_messages(
        self,
        sku_json: dict[str, Any],
        keyword_clusters: dict[str, Any],
        feature_blocks: list[dict[str, Any]],
        iwiss_fingerprint: str = "",
    ) -> dict[str, Any]:
        """Build the Claude API request body."""
        # Format input envelope per the spec
        input_envelope = json.dumps({
            "sku_json": sku_json,
            "keyword_clusters": keyword_clusters,
            "feature_blocks": feature_blocks,
            "category_template": "crimp",
            "iwiss_fingerprint": iwiss_fingerprint,
        }, ensure_ascii=False, indent=2)

        # Claude uses a different message format
        user_content = (
            f"<input_envelope>\n{input_envelope}\n</input_envelope>\n\n"
            "Produce the blog structure JSON only."
        )

        return {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 8192,
            "temperature": 0.3,
        }

    def _call_api(self, payload: dict[str, Any]) -> str:
        """Make Claude API call."""
        response = self.client.post_sync("/v1/messages", json_data=payload)
        # Claude returns content as list of content blocks
        content = response.get("content", [])
        if isinstance(content, list):
            raw = " ".join(
                block.get("text", "") for block in content if block.get("type") == "text"
            )
        else:
            raw = str(content)
        extracted = extract_json_from_text(raw)
        if extracted:
            return extracted
        return raw

    def run(
        self,
        sku_json: dict[str, Any],
        keyword_clusters: dict[str, Any],
        feature_blocks: list[dict[str, Any]],
        iwiss_fingerprint: str = "",
    ) -> dict[str, Any]:
        """Execute M3: produce blog structure JSON.

        Returns validated BlogStructure dict.
        """
        log.info("[M3] Calling Claude blog structure generation...")
        payload = self.build_messages(sku_json, keyword_clusters, feature_blocks, iwiss_fingerprint)

        raw_result = retry_with_json_fallback(
            lambda: self._call_api(payload),
            max_attempts=2,
        )
        parsed = json.loads(raw_result)
        validated = BlogStructure(**parsed)
        log.info("[M3] Claude complete: {} sections", len(validated.sections))
        return validated.model_dump()
