"""Canonical data model shared by every supplier adapter.

Every supplier returns its own raw schema. Adapters translate that into
`Offer`, so the comparison engine and the LLM layer only ever see one shape.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    BACKORDER = "backorder"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


def normalize_mpn(mpn: str | None) -> str | None:
    """'XPS9300-7909SLV', 'xps9300 7909slv' and 'XPS93007909SLV' all become 'xps93007909slv'."""
    if not mpn:
        return None
    return re.sub(r"[^a-z0-9]", "", mpn.lower()) or None


class Offer(BaseModel):
    """One purchasable product from one supplier."""

    # Identity
    supplier: str = Field(description="Supplier / data source name, e.g. 'DummyJSON'")
    supplier_product_id: str = Field(description="Supplier's own product ID")
    sku: str | None = None
    manufacturer_part_number: str | None = Field(
        default=None, description="Manufacturer part number (MPN) as the supplier wrote it"
    )
    product_name: str = Field(description="Display name (DummyJSON: `title`)")
    title: str = Field(description="Raw title as returned by the supplier")
    description: str | None = None
    brand: str | None = None
    category: str | None = None

    # Commercials
    price: float | None = Field(default=None, description="Unit list price; None if quote required")
    currency: str = "USD"
    discount_percentage: float | None = None
    effective_price: float | None = Field(
        default=None, description="Price after supplier discount, if any"
    )
    minimum_order_quantity: int = 1

    # Fulfilment
    availability: Availability = Availability.UNKNOWN
    availability_text: str | None = Field(default=None, description="Supplier's raw status string")
    stock_quantity: int | None = None
    delivery_estimate_days: int | None = Field(
        default=None, description="Parsed delivery estimate in days; None if not parseable"
    )
    shipping_information: str | None = Field(default=None, description="Raw shipping text")
    return_policy: str | None = None
    warranty_information: str | None = None

    # Quality signals
    rating: float | None = Field(default=None, ge=0, le=5)

    # Provenance / extras
    source_url: HttpUrl | None = None
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Supplier-specific extras (dimensions, weight, tags, ...)"
    )

    @property
    def match_key(self) -> str | None:
        """Key for spotting the same product at different suppliers."""
        return normalize_mpn(self.manufacturer_part_number)

    @property
    def is_purchasable(self) -> bool:
        return self.price is not None and self.availability in (
            Availability.IN_STOCK,
            Availability.LOW_STOCK,
        )
