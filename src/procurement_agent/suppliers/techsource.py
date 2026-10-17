"""TechSource Supply Co. adapter.

Source: data/suppliers/techsource.json (built by setup/generate_mock_suppliers.py)

Layout: nested. One record per item under `products`, split into blocks:
    product       {id, name, brand, identifiers {mpn, upc}, category {code, label},
                   long_description, attributes [{name, value}, ...]}
    pricing       {amount, currency} | null; amount may be null too
    availability  {status, quantity, lead_time_days}
                  status: available | low_stock | backorder | on_request | discontinued
    logistics     {delivery_window: "2-3 business days" | "5-6 weeks" | null, ships_from}
    rating        {average, count, scale} | null
    policies      {return_days, warranty_months}

Notes
    - Names are written inconsistently ("T7 Portable SSD 1TB | Samsung",
      "Microsoft LXM-00001 - Ergonomic Keyboard"). `title` keeps the raw name;
      `product_name` moves a trailing "| Brand" to the front so names read alike.
    - MPNs are reformatted at random (lowercase, dashes dropped or turned into
      spaces). `Offer.match_key` normalizes that away.
    - The delivery estimate is the upper end of `delivery_window`, falling back to
      `lead_time_days` when there is no window.
"""

from __future__ import annotations

from typing import Any

from procurement_agent.models import Availability, Offer
from procurement_agent.suppliers.dummyjson import parse_delivery_days
from procurement_agent.suppliers.local_file import LocalFileSupplier

SUPPLIER_NAME = "TechSource Supply Co."

_STATUS_MAP = {
    "available": Availability.IN_STOCK,
    "low_stock": Availability.LOW_STOCK,
    "backorder": Availability.BACKORDER,
    "discontinued": Availability.OUT_OF_STOCK,
    "on_request": Availability.UNKNOWN,
}

_STATUS_TEXT = {
    "available": "Available",
    "low_stock": "Low stock",
    "backorder": "Backordered",
    "discontinued": "Discontinued",
    "on_request": "Availability on request",
}


def map_availability(status: str | None) -> Availability:
    return _STATUS_MAP.get((status or "").strip().lower(), Availability.UNKNOWN)


def clean_name(name: str, brand: str | None) -> str:
    """'T7 Portable SSD 1TB | Samsung' -> 'Samsung T7 Portable SSD 1TB'."""
    if brand and name.endswith(f" | {brand}"):
        return f"{brand} {name[: -len(f' | {brand}')]}"
    return name

def to_offer(raw: dict[str, Any]) -> Offer:
    """Translate one TechSource product record into the canonical `Offer`."""
    product = raw.get("product") or {}
    pricing = raw.get("pricing") or {}
    availability = raw.get("availability") or {}
    logistics = raw.get("logistics") or {}
    rating = raw.get("rating") or {}
    policies = raw.get("policies") or {}
    identifiers = product.get("identifiers") or {}

    brand = product.get("brand")
    name = product.get("name", "")
    status = availability.get("status")
    window = logistics.get("delivery_window")
    delivery_days = parse_delivery_days(window)
    if delivery_days is None:
        delivery_days = availability.get("lead_time_days")

    avg = rating.get("average")
    scale = rating.get("scale") or 5
    rating_5 = round(avg * 5 / scale, 2) if avg is not None else None

    returns = policies.get("return_days")
    warranty = policies.get("warranty_months")

    attributes: dict[str, Any] = {
        a["name"]: a["value"] for a in product.get("attributes") or [] if "name" in a
    }
    if identifiers.get("upc"):
        attributes["upc"] = identifiers["upc"]
    if logistics.get("ships_from"):
        attributes["ships_from"] = logistics["ships_from"]
    if rating.get("count") is not None:
        attributes["review_count"] = rating["count"]
    if pricing.get("amount") is None:
        attributes["price_note"] = "Price on request"

    category = product.get("category") or {}

    #### THESE ARE THE FIELD MAPPINGS! Mapping the supplier fields to Offer schema 
    #### This is how we map all the supplier field names to a common schema 
    #### for example amount gets mapped to price         price=raw.get("amount"),
    return Offer(
        supplier=SUPPLIER_NAME,
        supplier_product_id=product["id"],
        sku=product["id"],
        manufacturer_part_number=identifiers.get("mpn"),
        product_name=clean_name(name, brand),
        title=name,
        description=product.get("long_description"),
        brand=brand,
        category=category.get("label"),
        price=pricing.get("amount"),
        currency=pricing.get("currency") or "USD",
        effective_price=pricing.get("amount"),
        minimum_order_quantity=raw.get("min_order_quantity") or 1,
        availability=map_availability(status),
        availability_text=_STATUS_TEXT.get(status, status),
        stock_quantity=availability.get("quantity"),
        delivery_estimate_days=delivery_days,
        shipping_information=window,
        return_policy=f"{returns}-day returns" if returns else None,
        warranty_information=f"{warranty} months" if warranty else None,
        rating=rating_5,
        attributes=attributes,
    )


class TechSourceSupplier(LocalFileSupplier):
    name = SUPPLIER_NAME
    default_file = "techsource.json"

    def records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return payload["products"]

    def to_offer(self, raw: dict[str, Any]) -> Offer:
        return to_offer(raw)

    def search_text(self, raw: dict[str, Any]) -> str:
        product = raw.get("product") or {}
        attrs = " ".join(
            f"{a.get('name', '')} {a.get('value', '')}" for a in product.get("attributes") or []
        )
        return " ".join(
            [
                product.get("name") or "",
                product.get("brand") or "",
                (product.get("identifiers") or {}).get("mpn") or "",
                (product.get("category") or {}).get("label") or "",
                product.get("long_description") or "",
                attrs,
            ]
        )
