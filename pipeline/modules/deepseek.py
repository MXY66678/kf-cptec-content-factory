"""M1 — DeepSeek Keyword Intelligence Module.

Clusters keywords by search intent using DeepSeek API.
Output: seo_keywords JSON validated against SEOKeywords schema.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger as log

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from pipeline.schemas.seo_schema import SEOKeywords
from pipeline.utils.http_client import APIClient
from pipeline.utils.retry import extract_json_from_text, retry_with_json_fallback


CLUSTERING_SYSTEM_PROMPT = """You are a search-intent analyst. Cluster keywords and classify intent. Output JSON only.

CLUSTERING LOGIC:
1. Group by semantic root (stem + tool/material/action entities).
2. Each cluster gets ONE intent label (informational|transactional|comparison|navigational).
3. high-freq keyword in each cluster = cluster primary.
4. Expand each cluster with 3-5 long-tail variants.
5. Flag cannibalization risk: clusters whose primaries would compete for the same SERP → mark "merge_candidate".

INTENT CLASSIFICATION RULES:
- informational: contains how/what/why/guide/vs-free explainers, no brand or buy modifiers
- transactional: buy/best/price/kit/size modifiers, brand+model queries
- comparison: "vs", "or", "difference", alternative tool names
- navigational: brand-only queries → excluded from blog mapping, routed to listing backend_keywords instead

OUTPUT JSON FORMAT:
{
  "intent_clusters": [
    {
      "cluster_name": "string",
      "intent": "informational|transactional|comparison|navigational",
      "primary": "string",
      "keywords": ["string"],
      "long_tail": ["string"],
      "merge_candidate": false,
      "mapped_section_type": "intro|tool_overview|how_to_step|comparison|faq|cta"
    }
  ],
  "density_targets": { "primary": "1-2%", "secondary": "0.5-1%" },
  "excluded_navigational": ["string"]
}"""


class DeepSeekModule:
    """M1 Keyword Intelligence module using DeepSeek API."""

    def __init__(self) -> None:
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY is not set")
        self.client = APIClient(
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
            timeout=180.0,
        )
        self.model = DEEPSEEK_MODEL

    def build_prompt(self, keyword_csv: str, sku_context: dict[str, Any]) -> list[dict[str, str]]:
        """Build the chat messages for DeepSeek clustering."""
        context_str = json.dumps(sku_context, ensure_ascii=False, indent=2)
        user_msg = (
            f"<keyword_table>{keyword_csv}</keyword_table>\n\n"
            f"<product_context>\n{context_str}\n</product_context>\n\n"
            "Cluster the keywords by search intent. Output JSON only."
        )
        return [
            {"role": "system", "content": CLUSTERING_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

    def _call_api(self, messages: list[dict[str, str]]) -> str:
        """Make the actual DeepSeek API call."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        response = self.client.post_sync("/chat/completions", json_data=payload)
        raw = response["choices"][0]["message"]["content"]
        extracted = extract_json_from_text(raw)
        if extracted:
            return extracted
        return raw

    def run(self, keyword_csv: str, sku_context: dict[str, Any]) -> dict[str, Any]:
        """Execute M1: cluster keywords using DeepSeek.

        Args:
            keyword_csv: Raw keyword table as CSV string.
            sku_context: SKU context dict with category, tool_type, pipe_materials.

        Returns:
            Validated SEOKeywords dict.
        """
        log.info("[M1] Calling DeepSeek keyword clustering...")
        messages = self.build_prompt(keyword_csv, sku_context)

        raw_result = retry_with_json_fallback(
            lambda: self._call_api(messages),
            max_attempts=2,
        )
        parsed = json.loads(raw_result)
        validated = SEOKeywords(**parsed)
        log.info("[M1] DeepSeek clustering complete: {} clusters", len(validated.intent_clusters))
        return validated.model_dump()
