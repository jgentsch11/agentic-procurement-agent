"""Tests for the NorthStar and TechSource adapters (local JSON files, no network)."""

import json

import pytest

from procurement_agent.models import Availability, Offer, normalize_mpn
from procurement_agent.suppliers import NorthStarSupplier, SupplierError, TechSourceSupplier
from procurement_agent.suppliers.northstar import to_offer as ns_to_offer
from procurement_agent.suppliers.techsource import clean_name
from procurement_agent.suppliers.techsource import to_offer as ts_to_offer


@pytest.fixture(scope="module")
def northstar():
    return NorthStarSupplier()


@pytest.fixture(scope="module")
def techsource():
    return TechSourceSupplier()


# -- whole catalog --------------------------------------------------------------


@pytest.mark.parametrize("supplier_cls", [NorthStarSupplier, TechSourceSupplier])
def test_every_record_converts(supplier_cls):
    offers = supplier_cls().all()
    assert len(offers) == 100
    assert all(isinstance(o, Offer) for o in offers)
    assert len({o.supplier_product_id for o in offers}) == 100
    assert all(o.product_name and o.manufacturer_part_number for o in offers)


@pytest.mark.parametrize("supplier_cls", [NorthStarSupplier, TechSourceSupplier])
def test_no_supplier_lists_a_product_twice(supplier_cls):
    keys = [o.match_key for o in supplier_cls().all()]
    assert len(keys) == len(set(keys))


def test_shared_products_match_despite_mpn_formatting(northstar, techsource):
    shared = {o.match_key for o in northstar.all()} & {o.match_key for o in techsource.all()}
    assert len(shared) == 46


def test_normalize_mpn():
    assert normalize_mpn("XPS9300-7909SLV") == normalize_mpn("xps9300 7909slv") == "xps93007909slv"
    assert normalize_mpn("DT70/64GB") == "dt7064gb"
    assert normalize_mpn(None) is None
    assert normalize_mpn("--") is None


# -- NorthStar edge cases ---------------------------------------------------------


def test_northstar_call_for_pricing(northstar):
    quotes = [o for o in northstar.all() if o.price is None]
    assert len(quotes) == 4
    assert all(o.attributes["price_note"] == "Call for pricing" for o in quotes)
    assert not any(o.is_purchasable for o in quotes)


def test_northstar_out_of_stock(northstar):
    out = [o for o in northstar.all() if o.availability == Availability.OUT_OF_STOCK]
    assert len(out) == 23
    assert all(o.availability_text == "Out of stock" for o in out)
    assert all(o.delivery_estimate_days is None for o in out)


def test_northstar_delivery_includes_transit():
    from procurement_agent.suppliers.northstar import delivery_estimate

    assert delivery_estimate(1, "Expedited") == (4, "Ships in 1 day, then Expedited 1-2 business days")
    assert delivery_estimate(3, "Freight")[0] == 13
    assert delivery_estimate(None, "Ground") == (None, None)


def test_northstar_missing_rating_and_order_minimums(northstar):
    offers = northstar.all()
    assert sum(o.rating is None for o in offers) == 5
    assert sorted(o.minimum_order_quantity for o in offers if o.minimum_order_quantity > 1) == [5, 10, 24]


def test_northstar_field_mapping():
    raw = {
        "item_number": "NS-1",
        "name": "Widget",
        "manufacturer": "Acme",
        "mfr_part_number": "W-1",
        "category_path": "A > B",
        "description": "d",
        "unit_price": 10.0,
        "price_note": None,
        "in_stock": True,
        "qty_available": 3,
        "ships_in_days": 2,
        "shipping_method": "Ground",
        "rating": 4.5,
        "review_count": 7,
        "return_window_days": 30,
        "warranty": "1 year",
        "min_order_qty": 1,
        "specs": {"ports": 4},
    }
    o = ns_to_offer(raw)
    assert o.price == 10.0
    assert o.availability == Availability.LOW_STOCK
    assert o.availability_text == "In stock (3 available)"
    assert o.delivery_estimate_days == 9  # ships in 2 days + Ground 3-5 business days (~7)
    assert o.shipping_information == "Ships in 2 days, then Ground 3-5 business days"
    assert o.return_policy == "30-day returns"
    assert o.attributes == {"ports": 4, "review_count": 7, "shipping_method": "Ground"}


# -- TechSource edge cases --------------------------------------------------------


def test_techsource_missing_prices(techsource):
    quotes = [o for o in techsource.all() if o.price is None]
    assert len(quotes) == 3  # 2 "on request" with no pricing block, 1 with a null amount
    assert all(o.attributes["price_note"] == "Price on request" for o in quotes)
    on_request = techsource.get("TS20021")
    assert on_request.availability == Availability.UNKNOWN
    assert on_request.delivery_estimate_days is None


def test_techsource_backorder_and_discontinued(techsource):
    by_status = {}
    for o in techsource.all():
        by_status.setdefault(o.availability_text, []).append(o)
    backorders = by_status["Backordered"]
    assert len(backorders) == 7
    assert all(o.availability == Availability.BACKORDER and not o.is_purchasable for o in backorders)
    assert all(o.delivery_estimate_days >= 21 for o in backorders)
    discontinued = by_status["Discontinued"]
    assert len(discontinued) == 2
    assert all(o.availability == Availability.OUT_OF_STOCK for o in discontinued)


def test_techsource_missing_rating_and_order_minimums(techsource):
    offers = techsource.all()
    assert sum(o.rating is None for o in offers) == 19
    assert sorted(o.minimum_order_quantity for o in offers if o.minimum_order_quantity > 1) == [10, 10, 25]


def test_techsource_delivery_uses_window_upper_bound(techsource):
    assert techsource.get("TS20066").delivery_estimate_days == 28  # "3-4 weeks"


def test_techsource_rating_rescaled_to_five():
    raw = {
        "product": {"id": "TS1", "name": "Widget", "brand": "Acme", "identifiers": {"mpn": "w1"}},
        "pricing": {"amount": 5.0, "currency": "USD"},
        "availability": {"status": "available", "quantity": 50, "lead_time_days": 2},
        "logistics": {"delivery_window": None},
        "rating": {"average": 8.0, "count": 3, "scale": 10},
        "policies": {},
    }
    o = ts_to_offer(raw)
    assert o.rating == 4.0
    assert o.delivery_estimate_days == 2  # falls back to lead time


def test_clean_name():
    assert clean_name("T7 Portable SSD 1TB | Samsung", "Samsung") == "Samsung T7 Portable SSD 1TB"
    assert clean_name("Microsoft LXM-00001 - Ergonomic Keyboard", "Microsoft") == (
        "Microsoft LXM-00001 - Ergonomic Keyboard"
    )


# -- search and lookup ------------------------------------------------------------


@pytest.mark.parametrize("supplier_cls", [NorthStarSupplier, TechSourceSupplier])
def test_search_requires_every_word(supplier_cls):
    hits = supplier_cls().search("usb-c dock")
    assert hits
    for o in hits:
        text = f"{o.title} {o.description} {o.category}".lower()
        assert "usb" in text and "dock" in text


def test_search_matches_plural(northstar):
    assert len(northstar.search("monitors")) == len(northstar.search("monitor"))


def test_search_no_match_and_empty_query(northstar):
    assert northstar.search("espresso machine") == []
    assert northstar.search("   ") == []


def test_search_limit(techsource):
    assert len(techsource.search("monitor", limit=3)) == 3


def test_get_unknown_id(northstar, techsource):
    assert northstar.get("NS-000000") is None
    assert techsource.get("nope") is None


def test_missing_or_broken_file_raises_supplier_error(tmp_path):
    with pytest.raises(SupplierError):
        NorthStarSupplier(tmp_path / "missing.json").all()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"wrong_key": []}))
    with pytest.raises(SupplierError):
        TechSourceSupplier(bad).all()
