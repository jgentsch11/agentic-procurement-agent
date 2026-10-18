"""Tests for the comparison engine (no network: DummyJSON is replaced by fakes)."""

import time

import pytest

from procurement_agent.comparison import (
    ScoringConfig,
    SearchRequest,
    compare,
    filter_offers,
    group_offers,
    score_offers,
    search_all,
)
from procurement_agent.models import Availability, Offer
from procurement_agent.suppliers import NorthStarSupplier, SupplierAdapter, SupplierError, TechSourceSupplier

CONFIG = ScoringConfig()


def make_offer(**kw) -> Offer:
    defaults = dict(
        supplier="Acme",
        supplier_product_id=kw.get("supplier_product_id", "1"),
        product_name="27 inch Monitor",
        title="27 inch Monitor",
        price=100.0,
        effective_price=kw.get("price", 100.0),
        availability=Availability.IN_STOCK,
        stock_quantity=50,
        delivery_estimate_days=3,
        rating=4.0,
    )
    defaults.update(kw)
    return Offer(**defaults)


class FakeSupplier(SupplierAdapter):
    def __init__(self, name, offers=(), error=None, delay=0.0):
        self.name = name
        self._offers = list(offers)
        self._error = error
        self._delay = delay

    def search(self, query, *, limit=20):
        time.sleep(self._delay)
        if self._error:
            raise SupplierError(self.name, self._error)
        return self._offers

    def get(self, product_id):
        return None


def local_suppliers():
    return [NorthStarSupplier(), TechSourceSupplier()]


# -- search -----------------------------------------------------------------------


def test_search_all_reports_failed_and_slow_suppliers():
    request = SearchRequest(search_terms=["monitor"])
    good = FakeSupplier("Good", [make_offer()])
    broken = FakeSupplier("Broken", error="HTTP 503")
    slow = FakeSupplier("Slow", [make_offer()], delay=2)

    started = time.monotonic()
    offers, statuses = search_all(request, [good, broken, slow], timeout=0.5)
    assert time.monotonic() - started < 1.5

    assert len(offers) == 1
    by_name = {s.supplier: s for s in statuses}
    assert by_name["Good"].ok and by_name["Good"].offers_found == 1
    assert not by_name["Broken"].ok and "503" in by_name["Broken"].error
    assert not by_name["Slow"].ok and by_name["Slow"].error == "timed out"


def test_search_all_merges_results_of_several_terms():
    request = SearchRequest(search_terms=["monitor", "display"])
    supplier = FakeSupplier("Acme", [make_offer()])  # returns the same item for both terms
    offers, _ = search_all(request, [supplier])
    assert len(offers) == 1


# -- filter -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes, request_kw, reason_start",
    [
        (dict(title="Saucepan", product_name="Saucepan"), {}, "Not a match"),
        ({}, dict(must_have=["usb-c"]), "Missing required feature: usb-c"),
        (dict(title="27 inch Gaming Monitor"), dict(exclude=["gaming"]), "Excluded: mentions gaming"),
        (dict(price=None, effective_price=None), {}, "No price listed"),
        (dict(availability=Availability.OUT_OF_STOCK, availability_text="Discontinued"), {}, "Unavailable (Discontinued)"),
        (dict(availability=Availability.BACKORDER, delivery_estimate_days=35), {}, "Backordered, about 35 days"),
        (dict(availability=Availability.UNKNOWN), {}, "Availability unknown"),
        (dict(stock_quantity=1), dict(quantity=2), "Only 1 in stock, 2 needed"),
        (dict(minimum_order_quantity=10), dict(quantity=2), "Minimum order is 10"),
        (dict(price=500.0, effective_price=500.0), dict(max_unit_price=450), "Over budget"),
    ],
)
def test_filter_drop_reasons(changes, request_kw, reason_start):
    request = SearchRequest(search_terms=["monitor"], **request_kw)
    kept, dropped = filter_offers([make_offer(**changes)], request, CONFIG)
    assert not kept
    assert dropped[0].reason.startswith(reason_start)


def test_filter_keeps_a_good_offer():
    kept, dropped = filter_offers([make_offer()], SearchRequest(search_terms=["27 monitor"]), CONFIG)
    assert len(kept) == 1 and not dropped


def test_filter_flags_suspiciously_low_price():
    offers = [
        make_offer(supplier_product_id=str(i), price=p, effective_price=p)
        for i, p in enumerate([300.0, 320.0, 340.0, 27.99])
    ]
    kept, dropped = filter_offers(offers, SearchRequest(search_terms=["monitor"]), CONFIG)
    assert len(kept) == 3
    assert dropped[0].offer.price == 27.99
    assert dropped[0].reason.startswith("Suspiciously low price")


# -- score ------------------------------------------------------------------------


def test_scoring_weights_and_scaling():
    cheap_slow = make_offer(supplier_product_id="a", price=100.0, effective_price=100.0, delivery_estimate_days=10, rating=4.0)
    pricey_fast = make_offer(supplier_product_id="b", price=200.0, effective_price=200.0, delivery_estimate_days=2, rating=4.0)
    scored = score_offers([cheap_slow, pricey_fast], SearchRequest(search_terms=["monitor"], quantity=3), CONFIG)

    by_id = {s.offer.supplier_product_id: s for s in scored}
    # price weight 0.40 beats delivery weight 0.30, ratings are equal (0.8 x 0.30)
    assert by_id["a"].score == pytest.approx(0.40 + 0.24)
    assert by_id["b"].score == pytest.approx(0.30 + 0.24)
    assert scored[0].offer.supplier_product_id == "a"
    assert by_id["a"].total_price == 300.0


def test_scoring_missing_rating_is_neutral():
    scored = score_offers([make_offer(rating=None)], SearchRequest(search_terms=["monitor"]), CONFIG)
    assert scored[0].rating_score == CONFIG.missing_rating_score


def test_weights_come_from_config():
    price_only = ScoringConfig(weights={"price": 1.0, "delivery": 0.0, "rating": 0.0})
    cheap = make_offer(supplier_product_id="a", price=100.0, effective_price=100.0, rating=1.0)
    rated = make_offer(supplier_product_id="b", price=150.0, effective_price=150.0, rating=5.0)
    scored = score_offers([cheap, rated], SearchRequest(search_terms=["monitor"]), price_only)
    assert scored[0].offer.supplier_product_id == "a"


# -- group ------------------------------------------------------------------------


def test_same_part_number_is_one_group_with_cheapest_marked():
    a = make_offer(supplier="NorthStar", supplier_product_id="1", manufacturer_part_number="ABC-1", price=120.0, effective_price=120.0)
    b = make_offer(supplier="TechSource", supplier_product_id="2", manufacturer_part_number="abc 1", price=110.0, effective_price=110.0)
    c = make_offer(supplier="TechSource", supplier_product_id="3", manufacturer_part_number="XYZ", price=90.0, effective_price=90.0)
    groups = group_offers(score_offers([a, b, c], SearchRequest(search_terms=["monitor"]), CONFIG))

    assert len(groups) == 2
    shared = next(g for g in groups if g.match_key == "abc1")
    assert len(shared.offers) == 2
    assert shared.cheapest_supplier == "TechSource"


# -- end to end on the mock data --------------------------------------------------


def test_compare_27_inch_monitors_on_mock_data():
    request = SearchRequest(search_terms=["27 monitor"], quantity=2, max_unit_price=450, exclude=["arm", "mount"])
    result = compare(request, suppliers=local_suppliers())

    assert all(s.ok for s in result.suppliers)
    assert result.groups
    assert [g.best.score for g in result.groups] == sorted((g.best.score for g in result.groups), reverse=True)
    for group in result.groups:
        for s in group.offers:
            assert s.offer.price <= 450 and s.offer.is_purchasable
    assert any(len(g.offers) == 2 for g in result.groups), "expected a product listed at both suppliers"
    reasons = " ".join(d.reason for d in result.dropped)
    assert "Suspiciously low price ($27.99" in reasons
    assert "Over budget" in reasons and "Backordered" in reasons


def test_compare_no_suitable_product():
    result = compare(SearchRequest(search_terms=["espresso machine"]), suppliers=local_suppliers())
    assert result.found_nothing
    assert not result.dropped


def test_compare_survives_a_supplier_outage():
    suppliers = local_suppliers() + [FakeSupplier("DummyJSON", error="HTTP 500")]
    result = compare(SearchRequest(search_terms=["usb-c dock"]), suppliers=suppliers)
    assert result.groups
    assert [s.ok for s in result.suppliers] == [True, True, False]


def test_scoring_config_file_loads():
    config = ScoringConfig.load()
    assert sum(config.weights.values()) == pytest.approx(1.0)
