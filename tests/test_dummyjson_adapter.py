"""Offline tests for the DummyJSON adapter (no network)."""

import httpx
import pytest

from procurement_agent.models import Availability
from procurement_agent.suppliers.dummyjson import (
    DummyJSONSupplier,
    map_availability,
    parse_delivery_days,
    to_offer,
)

SAMPLE = {
    "id": 1,
    "title": "Essence Mascara Lash Princess",
    "description": "Popular mascara.",
    "category": "beauty",
    "price": 9.99,
    "discountPercentage": 7.17,
    "rating": 4.94,
    "stock": 5,
    "tags": ["beauty", "mascara"],
    "brand": "Essence",
    "sku": "RCH45Q1A",
    "weight": 2,
    "dimensions": {"width": 23.17, "height": 14.43, "depth": 28.01},
    "warrantyInformation": "1 month warranty",
    "shippingInformation": "Ships in 1 month",
    "availabilityStatus": "Low Stock",
    "returnPolicy": "30 days return policy",
    "minimumOrderQuantity": 24,
}


def test_to_offer_maps_requested_fields():
    o = to_offer(SAMPLE)
    assert o.supplier == "DummyJSON"
    assert o.supplier_product_id == "1"
    assert o.product_name == o.title == "Essence Mascara Lash Princess"
    assert o.description == "Popular mascara."
    assert o.category == "beauty"
    assert o.brand == "Essence"
    assert o.sku == "RCH45Q1A"
    assert o.price == 9.99
    assert o.effective_price == 9.27
    assert o.rating == 4.94
    assert o.availability is Availability.LOW_STOCK
    assert o.availability_text == "Low Stock"
    assert o.stock_quantity == 5
    assert o.shipping_information == "Ships in 1 month"
    assert o.delivery_estimate_days == 30
    assert o.return_policy == "30 days return policy"
    assert o.minimum_order_quantity == 24
    assert str(o.source_url) == "https://dummyjson.com/products/1"
    assert o.attributes["dimensions"]["width"] == 23.17


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ships overnight", 1),
        ("Ships in 1 week", 7),
        ("Ships in 2 weeks", 14),
        ("Ships in 1 month", 30),
        ("Ships in 3-5 business days", 7),
        ("Ships in 3 days", 3),
        (None, None),
        ("Contact supplier", None),
    ],
)
def test_parse_delivery_days(text, expected):
    assert parse_delivery_days(text) == expected


@pytest.mark.parametrize(
    "status,stock,expected",
    [
        ("In Stock", 50, Availability.IN_STOCK),
        ("Low Stock", 3, Availability.LOW_STOCK),
        ("Out of Stock", 0, Availability.OUT_OF_STOCK),
        (None, 0, Availability.OUT_OF_STOCK),
        (None, 4, Availability.LOW_STOCK),
        (None, 40, Availability.IN_STOCK),
        (None, None, Availability.UNKNOWN),
    ],
)
def test_map_availability(status, stock, expected):
    assert map_availability(status, stock) == expected


def test_missing_price_becomes_quote_required():
    raw = {**SAMPLE, "price": None}
    o = to_offer(raw)
    assert o.price is None
    assert o.effective_price is None
    assert not o.is_purchasable


def test_search_uses_search_endpoint_and_select(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"products": [SAMPLE], "total": 1, "skip": 0, "limit": 20})

    client = httpx.Client(base_url="https://dummyjson.com", transport=httpx.MockTransport(handler))
    offers = DummyJSONSupplier(client=client).search("mascara", limit=20)
    assert len(offers) == 1
    assert "/products/search" in captured["url"]
    assert "q=mascara" in captured["url"]
    assert "select=" in captured["url"]


def test_search_empty_results_returns_empty_list():
    client = httpx.Client(
        base_url="https://dummyjson.com",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"products": [], "total": 0, "skip": 0, "limit": 20})
        ),
    )
    assert DummyJSONSupplier(client=client).search("monitor") == []


def test_server_error_raises_supplier_error():
    from procurement_agent.suppliers.base import SupplierError

    client = httpx.Client(
        base_url="https://dummyjson.com",
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    )
    with pytest.raises(SupplierError):
        DummyJSONSupplier(client=client).search("laptop")
