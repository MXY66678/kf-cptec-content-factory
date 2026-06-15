"""M2 — GPT Product Marketing Engine Module.

Extracts features, maps to benefits, produces Amazon listing blocks.
Output: amazon_listing_blocks JSON validated against inline schemas.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger as log
from pydantic import BaseModel, Field

from config import GPT_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from pipeline.utils.http_client import APIClient
from pipeline.utils.retry import extract_json_from_text, retry_with_json_fallback


# ── Pydantic models for M2 output ──────────────────────────────

class FeatureBlock(BaseModel):
    """Single feature → benefit mapping."""
    feature: str = Field(..., max_length=100)
    spec_value: str = Field(..., max_length=200)
    user_benefit: str = Field(..., max_length=300)
    proof_point: Optional[str] = None
    target_keyword: Optional[str] = None
    claim_risk: str = Field(default="none", pattern=r"^(none|needs_cert_citation|needs_legal_review)$")


class AmazonTitleSlot(BaseModel):
    """Amazon product title slot."""
    brief: str = Field(..., max_length=200)
    keyword: str = Field(..., max_length=100)
    max_chars: int = Field(default=200)


class BulletSlot(BaseModel):
    """Amazon bullet point."""
    feature_block_ref: str = Field(..., max_length=100)
    keyword: str = Field(..., max_length=100)
    max_chars: int = Field(default=250)


class APlusModule(BaseModel):
    """Amazon A+ content module plan."""
    module_type: str = Field(..., max_length=50)
    brief: str = Field(..., max_length=200)
    image_slot: Optional[str] = None


class ClaimFlag(BaseModel):
    """Legal review flag."""
    field: str
    claim_risk: str = Field(..., pattern=r"^needs_legal_review$")


class WalmartBlocks(BaseModel):
    """Walmart listing structure."""
    title_slot: dict[str, Any] = Field(default_factory=lambda: {"brief": "", "max_chars": 80})
    rich_attributes: dict[str, str] = Field(default_factory=dict)
    shelf_description_brief: str = Field(default="", max_length=300)


class AdCopyVariant(BaseModel):
    """Ad copy variant for different channels."""
    channel: str = Field(..., pattern=r"^(ppc|walmart_sp|social)$")
    headline_brief: str = Field(..., max_length=100)
    body_brief: str = Field(..., max_length=200)


class AmazonListingBlocks(BaseModel):
    """Complete Amazon listing blocks output from M2."""
    title_slot: AmazonTitleSlot
    bullet_slots: list[BulletSlot] = Field(..., min_length=1, max_length=5)
    backend_keywords: list[str] = Field(default_factory=list)
    a_plus_modules: list[APlusModule] = Field(default_factory=list)
    claim_flags: list[ClaimFlag] = Field(default_factory=list)
    walmart_blocks: WalmartBlocks = Field(default_factory=WalmartBlocks)
    ad_copy_variants: list[AdCopyVariant] = Field(default_factory=list)


class FeatureBlocksOutput(BaseModel):
    """Complete M2 feature extraction output."""
    feature_blocks: list[FeatureBlock] = Field(..., min_length=1)
    ranked_order: list[str] = Field(default_factory=list)
    amazon_listing_blocks: AmazonListingBlocks


# ── GPT System Prompts ─────────────────────────────────────────

FEATURE_EXTRACTION_SYSTEM = """You extract product features and map them to user benefits.
Structure only — no ad prose, no superlatives without spec basis.
Output JSON only.

For each feature output:
{feature, spec_value, user_benefit, proof_point, target_keyword, claim_risk}
claim_risk = "none" | "needs_cert_citation" | "needs_legal_review"
Rank features by purchase-decision weight for the category."""

LISTING_STRUCTURE_SYSTEM = """You produce listing STRUCTURE blocks (slots + briefs + keyword assignments), not finished copy. Output JSON only.

RULES:
- Amazon title slot: brand + tool_type + top-2 specs + size, <=200 chars, primary keyword position 1-3 words.
- 5 bullet slots: each = 1 ranked feature_block, lead word in caps, assigned_keyword per bullet, <=250 chars each.
- backend_keywords: navigational + misspellings + synonyms, <=249 bytes, no repeats.
- A+ module plan: module_type + content_brief + image_slot ref.
- Walmart variant: rich attributes map, shelf description brief, 80-char title constraint.
- ad_copy_variants: headline/body briefs per channel (ppc | walmart_sp | social)."""


class GPTModule:
    """M2 Product Marketing Engine using OpenAI GPT API."""

    def __init__(self) -> None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")
        self.client = APIClient(
            base_url=OPENAI_BASE_URL,
            api_key=OPENAI_API_KEY,
            timeout=180.0,
        )
        self.model = GPT_MODEL

    def _call_api(self, messages: list[dict[str, str]]) -> str:
        """Make GPT API call."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        response = self.client.post_sync("/v1/chat/completions", json_data=payload)
        raw = response["choices"][0]["message"]["content"]
        extracted = extract_json_from_text(raw)
        if extracted:
            return extracted
        return raw

    def run(
        self,
        sku_json: dict[str, Any],
        transactional_clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute M2: feature extraction + listing blocks.

        Args:
            sku_json: Canonical SKU data.
            transactional_clusters: Transactional intent clusters from M1.

        Returns:
            Validated FeatureBlocksOutput dict including amazon_listing_blocks.
        """
        log.info("[M2] Calling GPT feature extraction...")
        sku_str = json.dumps(sku_json, ensure_ascii=False, indent=2)
        tx_str = json.dumps(transactional_clusters, ensure_ascii=False, indent=2)

        # Step 1: Feature extraction
        feature_messages = [
            {"role": "system", "content": FEATURE_EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"<sku_json>{sku_str}</sku_json>\n"
                    f"<transactional_clusters>{tx_str}</transactional_clusters>\n\n"
                    "Extract features and map to benefits. Output JSON only."
                ),
            },
        ]
        features_raw = retry_with_json_fallback(
            lambda: self._call_api(feature_messages),
            max_attempts=2,
        )
        features_parsed = json.loads(features_raw)

        # Step 2: Listing structure
        log.info("[M2] Calling GPT listing structure...")
        listing_messages = [
            {"role": "system", "content": LISTING_STRUCTURE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"<feature_blocks>{json.dumps(features_parsed.get('feature_blocks', []), ensure_ascii=False)}</feature_blocks>\n"
                    f"<transactional_clusters>{tx_str}</transactional_clusters>\n\n"
                    "Produce listing structure blocks. Output JSON only."
                ),
            },
        ]
        listing_raw = retry_with_json_fallback(
            lambda: self._call_api(listing_messages),
            max_attempts=2,
        )
        listing_parsed = json.loads(listing_raw)

        # Merge
        merged = {
            "feature_blocks": features_parsed.get("feature_blocks", []),
            "ranked_order": features_parsed.get("ranked_order", []),
            "amazon_listing_blocks": listing_parsed,
        }
        validated = FeatureBlocksOutput(**merged)
        log.info("[M2] GPT complete: {} feature blocks", len(validated.feature_blocks))
        return validated.model_dump()
