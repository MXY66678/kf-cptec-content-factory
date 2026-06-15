"""SKU canonical schema — Pydantic models for SKU data."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SKUSpec(BaseModel):
    """Individual specification entry."""
    name: str = Field(..., description="Spec name, e.g. 'Jaw Size'")
    value: str = Field(..., description="Spec value, e.g. '1/2 inch'")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class SKUBundleItem(BaseModel):
    """Item in the kit/bundle."""
    name: str
    quantity: int = Field(default=1, ge=1)
    sku: Optional[str] = None


class SKUCertification(BaseModel):
    """Certification or compliance standard."""
    standard: str = Field(..., description="e.g. 'ASTM F1807'")
    body: Optional[str] = None
    description: Optional[str] = None


class Variant(BaseModel):
    """SKU variant (e.g. different jaw size)."""
    sku_id: str
    description: str
    specs: list[SKUSpec] = Field(default_factory=list)
    upc: Optional[str] = None


class SKUCanonical(BaseModel):
    """Canonical SKU schema — normalized from raw input."""
    sku_id: str = Field(..., pattern=r"^KF-CPTEC-\w+$")
    product_name: str = Field(..., max_length=200)
    brand: str = Field(default="KF CPTEC")
    category: str = Field(..., description="crimp / press / cutter / expander")
    tool_type: str = Field(..., description="e.g. 'PEX Crimp Tool'")
    pipe_materials: list[str] = Field(default_factory=list)
    specs: list[SKUSpec] = Field(default_factory=list)
    bundle_contents: list[SKUBundleItem] = Field(default_factory=list)
    certifications: list[SKUCertification] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    upc: Optional[str] = None
    weight_lbs: Optional[float] = None
    dimensions: Optional[str] = None
    warranty: Optional[str] = None
    price_msrp: Optional[float] = None
    color: Optional[str] = None
    material: Optional[str] = None

    @field_validator("sku_id")
    @classmethod
    def validate_sku_id(cls, v: str) -> str:
        if not v.startswith("KF-CPTEC-"):
            raise ValueError(f"SKU ID must start with KF-CPTEC-, got {v}")
        return v

    model_config = {"extra": "ignore", "populate_by_name": True}
