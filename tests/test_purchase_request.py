"""Tests for the structured purchase request and its email draft."""

from datetime import datetime

import pytest

from procurement_agent.comparison import ScoredOffer
from procurement_agent.models import Availability, Offer
from procurement_agent.purchase_request import (
    PROCUREMENT_INBOX,
    Requester,
    build_purchase_request,
    email_draft,
)

NOW = datetime(2026, 10, 19, 9, 30, 15)


def scored(**kw) -> ScoredOffer:
    offer = Offer(
        supplier=kw.get("supplier", "NorthStar Office Supply"),
        supplier_product_id=kw.get("id", "NS-1"),
        manufacturer_part_number="ABC-1",
        product_name=kw.get("name", "Dell 27 Monitor"),
        title=kw.get("name", "Dell 27 Monitor"),
        price=kw.get("price", 200.0),
        effective_price=kw.get("price", 200.0),
        minimum_order_quantity=kw.get("moq", 1),
        availability=Availability.IN_STOCK,
        delivery_estimate_days=4,
        warranty_information="3 years",
        return_policy="30-day returns",
    )
    return ScoredOffer(offer=offer, score=0.9, price_score=1, delivery_score=1, rating_score=0.8, total_price=offer.price or 0)


def test_build_purchase_request():
    alt = scored(supplier="TechSource Supply Co.", id="TS-9", name="Acer 27 Monitor", price=190.0)
    pr = build_purchase_request(
        scored(), 2, Requester(name="Joe", department="IT", cost_center="CC-100"),
        "  two office monitors ", "Best overall score.", alternatives=[scored(), alt], now=NOW,
    )
    assert pr.request_id.startswith("PR-20261019-")
    assert pr.total_price == 400.0
    assert pr.status == "Draft - pending approval"
    assert pr.original_request == "two office monitors"
    # the chosen offer itself is not listed as an alternative
    assert pr.alternatives_considered == ["Acer 27 Monitor from TechSource Supply Co. at $190.00 per unit"]


def test_quantity_below_minimum_is_rejected():
    with pytest.raises(ValueError, match="at least 5"):
        build_purchase_request(scored(moq=5), 2, Requester(), "x", "y", now=NOW)


def test_offer_without_price_is_rejected():
    with pytest.raises(ValueError, match="no price"):
        build_purchase_request(scored(price=None), 1, Requester(), "x", "y", now=NOW)


def test_email_draft_contains_the_key_facts():
    pr = build_purchase_request(scored(), 2, Requester(name="Joe"), "two monitors", "Best overall score.", now=NOW)
    email = email_draft(pr)
    assert email.startswith(f"To: {PROCUREMENT_INBOX}\nSubject: Purchase request {pr.request_id}: 2 x Dell 27 Monitor")
    for fact in ["$200.00 USD", "$400.00 USD", "about 4 days", "Requested by:   Joe", "Cost center:    (not given)",
                 "Best overall score.", "Draft - pending approval"]:
        assert fact in email
    assert "ALTERNATIVES CONSIDERED" not in email
