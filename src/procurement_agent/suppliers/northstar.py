"""NorthStar Office Supply adapter.

Source: data/suppliers/northstar_office.json (built by setup/generate_mock_suppliers.py)

Layout: flat. One record per item under `items`, for example
    unit_price: 57.82 | null        price_note: "Call for pricing" when unit_price is null
    in_stock: true                  qty_available: 3
    ships_in_days: 7 | null         (null when out of stock)

Notes
    - NorthStar only publishes when an item ships, not when it arrives. To compare
      like for like with TechSource's delivery window, the delivery estimate is
      `ships_in_days` plus the transit time for the shipping method (TRANSIT_WINDOWS),
      with business days converted to calendar days the same way as the other adapters.
    - Fewer than 10 units in stock is reported as low stock, the same threshold the
      DummyJSON adapter uses.
"""

from __future__ import annotations

from typing import Any

from procurement_agent.models import Availability, Offer
from procurement_agent.suppliers.dummyjson import parse_delivery_days
from procurement_agent.suppliers.local_file import LocalFileSupplier

SUPPLIER_NAME = "NorthStar Office Supply"
LOW_STOCK_BELOW = 10

# Assumed carrier transit time per shipping method, added after the item ships.
TRANSIT_WINDOWS = {
    "Expedited": "1-2 business days",
    "Ground": "3-5 business days",
    "Freight": "5-7 business days",
}
DEFAULT_TRANSIT = TRANSIT_WINDOWS["Ground"]


def delivery_estimate(ships_in_days: int | None, method: str | None) -> tuple[int | None, str | None]:
    """Days until delivery, and the text shown for it.

    Ships in 7 days by Ground (3-5 business days, about 7 calendar days) -> 14.
    """
    if ships_in_days is None:
        return None, None
    transit = TRANSIT_WINDOWS.get(method or "", DEFAULT_TRANSIT)
    days = ships_in_days + (parse_delivery_days(transit) or 0)
    label = f"Ships in {ships_in_days} day{'s' if ships_in_days != 1 else ''}"
    return days, f"{label}, then {method or 'Ground'} {transit}"


def map_availability(in_stock: bool | None, qty: int | None) -> Availability:
    if in_stock is None:
        return Availability.UNKNOWN
    if not in_stock or (qty is not None and qty <= 0):
        return Availability.OUT_OF_STOCK
    if qty is not None and qty < LOW_STOCK_BELOW:
        return Availability.LOW_STOCK
    return Availability.IN_STOCK


def to_offer(raw: dict[str, Any]) -> Offer:
    """Translate one NorthStar item into the canonical `Offer`."""
    qty = raw.get("qty_available")
    in_stock = raw.get("in_stock")
    ships_in = raw.get("ships_in_days")
    method = raw.get("shipping_method")
    returns = raw.get("return_window_days")

    if in_stock:
        availability_text = f"In stock ({qty} available)" if qty is not None else "In stock"
    elif in_stock is False:
        availability_text = "Out of stock"
    else:
        availability_text = None

    delivery_days, shipping = delivery_estimate(ships_in, method)

    attributes: dict[str, Any] = dict(raw.get("specs") or {})
    for key in ("price_note", "review_count", "shipping_method"):
        if raw.get(key) is not None:
            attributes[key] = raw[key]

    #### THESE ARE THE FIELD MAPPINGS! Mapping the supplier fields to Offer schema 
    #### This is how we map all the supplier field names to a common schema 
    #### for example unit_price gets mapped to price         price=raw.get("unit_price"),
    return Offer(
        supplier=SUPPLIER_NAME,
        supplier_product_id=raw["item_number"],
        sku=raw["item_number"],
        manufacturer_part_number=raw.get("mfr_part_number"),
        product_name=raw.get("name", ""),
        title=raw.get("name", ""),
        description=raw.get("description"),
        brand=raw.get("manufacturer"),
        category=raw.get("category_path"),
        price=raw.get("unit_price"),
        currency="USD",
        effective_price=raw.get("unit_price"),
        minimum_order_quantity=raw.get("min_order_qty") or 1,
        availability=map_availability(in_stock, qty),
        availability_text=availability_text,
        stock_quantity=qty,
        delivery_estimate_days=delivery_days,
        shipping_information=shipping,
        return_policy=f"{returns}-day returns" if returns else None,
        warranty_information=raw.get("warranty"),
        rating=raw.get("rating"),
        attributes=attributes,
    )


class NorthStarSupplier(LocalFileSupplier):
    name = SUPPLIER_NAME
    default_file = "northstar_office.json"

    def records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return payload["items"]

    def to_offer(self, raw: dict[str, Any]) -> Offer:
        return to_offer(raw)

    def search_text(self, raw: dict[str, Any]) -> str:
        specs = " ".join(str(v) for v in (raw.get("specs") or {}).values())
        return " ".join(
            str(raw.get(k) or "")
            for k in ("name", "manufacturer", "mfr_part_number", "category_path", "description")
        ) + " " + specs
