"""DummyJSON supplier adapter.

Docs: https://dummyjson.com/docs/products

Endpoints used
    GET /products/search?q=<text>&limit=&skip=&select=   free-text search
    GET /products/<id>?select=                            single product
    GET /products/category/<slug>?limit=&select=          browse a category

Notes
    - Public, no API key, read-only. Writes (POST/PUT/DELETE) are simulated and
      never persist, so this adapter is search-only.
    - `select` trims the payload server-side; we request only the fields we map.
    - Catalog is consumer goods (laptops, tablets, smartphones, mobile-accessories
      are the closest fit to IT equipment). There are no monitors or docking
      stations, which is useful for demonstrating the "no suitable product" path.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from procurement_agent.models import Availability, Offer
from procurement_agent.suppliers.base import SupplierAdapter, SupplierError

BASE_URL = "https://dummyjson.com"
SUPPLIER_NAME = "DummyJSON"

# Fields we ask the API to return. Anything not listed here is dropped server-side.
SELECT_FIELDS = (
    "id,title,description,category,price,discountPercentage,rating,stock,brand,sku,"
    "availabilityStatus,shippingInformation,returnPolicy,warrantyInformation,"
    "minimumOrderQuantity,tags,weight,dimensions,thumbnail"
)

_AVAILABILITY_MAP = {
    "in stock": Availability.IN_STOCK,
    "low stock": Availability.LOW_STOCK,
    "out of stock": Availability.OUT_OF_STOCK,
}

_DURATION_RE = re.compile(
    r"(?P<n>\d+)\s*(?P<unit>day|days|week|weeks|month|months|business day|business days)",
    re.IGNORECASE,
)
_UNIT_DAYS = {
    "day": 1,
    "week": 7,
    "month": 30,
    "business day": 1.4,  # ~7 calendar days per 5 business days
}


def parse_delivery_days(text: str | None) -> int | None:
    """'Ships in 2 weeks' -> 14, 'Ships overnight' -> 1, 'Ships in 3-5 business days' -> 7."""
    if not text:
        return None
    lowered = text.lower()
    if "overnight" in lowered:
        return 1
    # Ranges like "3-5 business days": take the upper bound (conservative estimate).
    range_match = re.search(r"(\d+)\s*-\s*(\d+)\s*(business day|day|week|month)", lowered)
    if range_match:
        n = int(range_match.group(2))
        unit = range_match.group(3)
        return round(n * _UNIT_DAYS[unit])
    m = _DURATION_RE.search(lowered)
    if not m:
        return None
    n = int(m.group("n"))
    unit = m.group("unit").rstrip("s")
    return round(n * _UNIT_DAYS[unit])


def map_availability(status: str | None, stock: int | None) -> Availability:
    if status:
        mapped = _AVAILABILITY_MAP.get(status.strip().lower())
        if mapped:
            return mapped
    if stock is None:
        return Availability.UNKNOWN
    if stock <= 0:
        return Availability.OUT_OF_STOCK
    if stock < 10:
        return Availability.LOW_STOCK
    return Availability.IN_STOCK


def to_offer(raw: dict[str, Any]) -> Offer:
    """Translate one DummyJSON product record into the canonical `Offer`."""
    price = raw.get("price")
    discount = raw.get("discountPercentage")
    effective = None
    if price is not None:
        effective = round(price * (1 - (discount or 0) / 100), 2)

    shipping = raw.get("shippingInformation")
    stock = raw.get("stock")

    return Offer(
        supplier=SUPPLIER_NAME,
        supplier_product_id=str(raw["id"]),
        sku=raw.get("sku"),
        product_name=raw.get("title", ""),
        title=raw.get("title", ""),
        description=raw.get("description"),
        brand=raw.get("brand"),
        category=raw.get("category"),
        price=price,
        currency="USD",
        discount_percentage=discount,
        effective_price=effective,
        minimum_order_quantity=raw.get("minimumOrderQuantity") or 1,
        availability=map_availability(raw.get("availabilityStatus"), stock),
        availability_text=raw.get("availabilityStatus"),
        stock_quantity=stock,
        delivery_estimate_days=parse_delivery_days(shipping),
        shipping_information=shipping,
        return_policy=raw.get("returnPolicy"),
        warranty_information=raw.get("warrantyInformation"),
        rating=raw.get("rating"),
        source_url=f"{BASE_URL}/products/{raw['id']}",
        attributes={
            k: raw[k]
            for k in ("tags", "weight", "dimensions", "thumbnail")
            if k in raw and raw[k] is not None
        },
    )


class DummyJSONSupplier(SupplierAdapter):
    name = SUPPLIER_NAME

    def __init__(self, client: httpx.Client | None = None, timeout: float = 10.0):
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=timeout)

    # -- public API ---------------------------------------------------------

    def search(self, query: str, *, limit: int = 20) -> list[Offer]:
        data = self._get(
            "/products/search",
            params={"q": query, "limit": limit, "select": SELECT_FIELDS},
        )
        return [to_offer(p) for p in data.get("products", [])]

    def get(self, product_id: str) -> Offer | None:
        try:
            data = self._get(f"/products/{product_id}", params={"select": SELECT_FIELDS})
        except SupplierError as exc:
            if "404" in str(exc):
                return None
            raise
        return to_offer(data)

    def browse_category(self, slug: str, *, limit: int = 0) -> list[Offer]:
        """limit=0 returns every product in the category."""
        data = self._get(
            f"/products/category/{slug}",
            params={"limit": limit, "select": SELECT_FIELDS},
        )
        return [to_offer(p) for p in data.get("products", [])]

    def categories(self) -> list[str]:
        return self._get("/products/category-list")

    # -- internals ----------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            resp = self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise SupplierError(self.name, f"HTTP {exc.response.status_code} for {path}") from exc
        except httpx.TimeoutException as exc:
            raise SupplierError(self.name, f"timeout for {path}") from exc
        except httpx.HTTPError as exc:
            raise SupplierError(self.name, f"transport error for {path}: {exc}") from exc
        except ValueError as exc:
            raise SupplierError(self.name, f"malformed JSON for {path}") from exc
