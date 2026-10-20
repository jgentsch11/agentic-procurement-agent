"""Comparison engine: search every supplier, filter, score and group offers.

Everything here is plain code. The LLM (added later) only produces the
`SearchRequest` going in and explains the `ComparisonResult` coming out, so
every number, filter and ranking decision is reproducible and auditable.

Flow
    search_all     query every supplier in parallel, each with a timeout
    filter_offers  drop unsuitable offers, keeping the reason for each
    score_offers   rank what is left by price, delivery speed and rating
    group_offers   put the same product from different suppliers in one row
"""

from __future__ import annotations

import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

from pydantic import BaseModel, Field

from procurement_agent.models import Availability, Offer
from procurement_agent.suppliers import (
    DummyJSONSupplier,
    NorthStarSupplier,
    SupplierAdapter,
    SupplierError,
    TechSourceSupplier,
)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scoring.json"


# -- data shapes ------------------------------------------------------------------
#####
##### This is the structured parameters that the LLM fills in from the user's request####
####
class SearchRequest(BaseModel):
    """What the user wants, in structured form. The LLM fills this in later."""

    search_terms: list[str] = Field(description="Keyword searches to run, e.g. ['27 monitor']")
    quantity: int = Field(default=1, ge=1)
    max_unit_price: float | None = Field(default=None, description="Budget per unit, USD")
    must_have: list[str] = Field(
        default_factory=list, description="Words every offer must mention, e.g. ['usb-c']"
    )
    exclude: list[str] = Field(
        default_factory=list, description="Words that rule an offer out, e.g. ['gaming']"
    )


class ScoringConfig(BaseModel):
    weights: dict[str, float] = {"price": 0.40, "delivery": 0.30, "rating": 0.30}
    missing_rating_score: float = 0.5
    suspicious_price_ratio: float = 0.30
    supplier_timeout_seconds: float = 8

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "ScoringConfig":
        if path.exists():
            return cls.model_validate(json.loads(path.read_text()))
        return cls()

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(json.dumps(self.model_dump(), indent=2) + "\n")


class SupplierStatus(BaseModel):
    supplier: str
    ok: bool
    offers_found: int = 0
    error: str | None = None
    duration_ms: int | None = Field(default=None, description="How long this supplier took")


class DroppedOffer(BaseModel):
    offer: Offer
    reason: str


class ScoredOffer(BaseModel):
    offer: Offer
    score: float = Field(description="0 to 1, higher is better")
    price_score: float
    delivery_score: float
    rating_score: float
    total_price: float = Field(description="Unit price x quantity")


class ProductGroup(BaseModel):
    """One product, with one offer per supplier that carries it."""

    product_name: str
    match_key: str | None
    offers: list[ScoredOffer] = Field(description="Best score first")
    cheapest_supplier: str

    @property
    def best(self) -> ScoredOffer:
        return self.offers[0]


class ComparisonResult(BaseModel):
    request: SearchRequest
    groups: list[ProductGroup] = Field(description="Best product first")
    dropped: list[DroppedOffer]
    suppliers: list[SupplierStatus]

    @property
    def found_nothing(self) -> bool:
        return not self.groups


# -- 1. search --------------------------------------------------------------------


def default_suppliers() -> list[SupplierAdapter]:
    return [NorthStarSupplier(), TechSourceSupplier(), DummyJSONSupplier()]


def _search_one(supplier: SupplierAdapter, terms: list[str]) -> list[Offer]:
    seen: dict[str, Offer] = {}
    for term in terms:
        for offer in supplier.search(term):
            seen.setdefault(offer.supplier_product_id, offer)
    return list(seen.values())


def _search_timed(supplier: SupplierAdapter, terms: list[str]) -> tuple[list[Offer], SupplierError | None, int]:
    """Search one supplier and time it, so the audit log can show each supplier's duration."""
    start = time.perf_counter()
    try:
        found, error = _search_one(supplier, terms), None
    except SupplierError as exc:
        found, error = [], exc
    return found, error, round((time.perf_counter() - start) * 1000)


def search_all(
    request: SearchRequest,
    suppliers: list[SupplierAdapter],
    timeout: float = 8,
) -> tuple[list[Offer], list[SupplierStatus]]:
    """Query every supplier at once. A slow or failing supplier never blocks the others."""
    pool = ThreadPoolExecutor(max_workers=len(suppliers) or 1)
    futures = {pool.submit(_search_timed, s, request.search_terms): s for s in suppliers}
    done, _ = wait(futures, timeout=timeout)
    pool.shutdown(wait=False, cancel_futures=True)

    offers: list[Offer] = []
    statuses: list[SupplierStatus] = []
    for future, supplier in futures.items():
        if future not in done:
            statuses.append(
                SupplierStatus(supplier=supplier.name, ok=False, error="timed out", duration_ms=round(timeout * 1000))
            )
            continue
        found, error, ms = future.result()
        if error:
            statuses.append(SupplierStatus(supplier=supplier.name, ok=False, error=str(error), duration_ms=ms))
            continue
        offers += found
        statuses.append(SupplierStatus(supplier=supplier.name, ok=True, offers_found=len(found), duration_ms=ms))
    return offers, statuses


# -- 2. filter --------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> set[str]:
    words = set(_WORD_RE.findall(text.lower()))
    return words | {w[:-1] for w in words if w.endswith("s")}


def _offer_words(offer: Offer) -> set[str]:
    attrs = " ".join(f"{k} {v}" for k, v in offer.attributes.items())
    return _words(
        " ".join(
            filter(
                None,
                [offer.title, offer.product_name, offer.brand, offer.category, offer.description, attrs],
            )
        )
    )


def _mentions(offer_words: set[str], phrase: str) -> bool:
    return _words(phrase) <= offer_words


def _matches_search(offer: Offer, offer_words: set[str], term: str) -> bool:
    """Every word of the search appears in the listing, or inside its category name.

    The category check lets "phone" match a product filed under "smartphones"
    (an "iPhone 13 Pro" never says "phone" in its own title).
    """
    category_words = _words(offer.category or "")
    return all(
        word in offer_words or any(word in c for c in category_words) for word in _words(term)
    )


def _price(offer: Offer) -> float | None:
    return offer.effective_price if offer.effective_price is not None else offer.price

####
#### every result’s title, brand, category, description and specs are split into words. 
#### If any exclude word appears as a whole word the item is dropped.
####
def relevance_reason(offer: Offer, request: SearchRequest) -> str | None:
    """Is this the kind of product that was asked for? None means yes."""
    words = _offer_words(offer)
    if not any(_matches_search(offer, words, term) for term in request.search_terms):
        return "Not a match for the search (supplier returned an unrelated item)"
    missing = [m for m in request.must_have if not _mentions(words, m)]
    if missing:
        return f"Missing required feature: {', '.join(missing)}"
    excluded = [x for x in request.exclude if _mentions(words, x)]
    if excluded:
        return f"Excluded: mentions {', '.join(excluded)}"
    return None


def drop_reason(offer: Offer, request: SearchRequest, typical_price: float | None, config: ScoringConfig) -> str | None:
    """Why this offer is unsuitable, or None if it stays in."""
    reason = relevance_reason(offer, request)
    if reason:
        return reason

    price = _price(offer)
    if price is None:
        return "No price listed (quote required)"
    if offer.availability == Availability.OUT_OF_STOCK:
        return f"Unavailable ({offer.availability_text or 'out of stock'})"
    if offer.availability == Availability.BACKORDER:
        days = f", about {offer.delivery_estimate_days} days" if offer.delivery_estimate_days else ""
        return f"Backordered{days}"
    if offer.availability == Availability.UNKNOWN:
        return "Availability unknown"
    if offer.stock_quantity is not None and offer.stock_quantity < request.quantity:
        return f"Only {offer.stock_quantity} in stock, {request.quantity} needed"
    if offer.minimum_order_quantity > request.quantity:
        return f"Minimum order is {offer.minimum_order_quantity}, {request.quantity} needed"
    if request.max_unit_price is not None and price > request.max_unit_price:
        return f"Over budget (${price:,.2f} vs ${request.max_unit_price:,.2f} per unit)"
    if typical_price and price < typical_price * config.suspicious_price_ratio:
        return f"Suspiciously low price (${price:,.2f} vs typical ${typical_price:,.2f}), needs review"
    return None


def filter_offers(
    offers: list[Offer], request: SearchRequest, config: ScoringConfig
) -> tuple[list[Offer], list[DroppedOffer]]:
    # The typical price is the median of the relevant, priced offers, so one wildly
    # low listing stands out against its peers.
    peers = [p for o in offers if (p := _price(o)) is not None and relevance_reason(o, request) is None]
    typical = statistics.median(peers) if len(peers) >= 3 else None

    kept: list[Offer] = []
    dropped: list[DroppedOffer] = []
    for offer in offers:
        reason = drop_reason(offer, request, typical, config)
        if reason:
            dropped.append(DroppedOffer(offer=offer, reason=reason))
        else:
            kept.append(offer)
    return kept, dropped


# -- 3. score ---------------------------------------------------------------------


def _scaled(value: float | None, low: float, high: float, *, lower_is_better: bool) -> float:
    if value is None:
        return 0.0
    if high == low:
        return 1.0
    fraction = (value - low) / (high - low)
    return round(1 - fraction if lower_is_better else fraction, 4)


def score_offers(offers: list[Offer], request: SearchRequest, config: ScoringConfig) -> list[ScoredOffer]:
    """Each factor is scaled 0 to 1 across the offers being compared, then weighted."""
    if not offers:
        return []
    prices = [_price(o) for o in offers]
    days = [o.delivery_estimate_days for o in offers if o.delivery_estimate_days is not None]
    w = config.weights

    scored = []
    for offer, price in zip(offers, prices):
        price_score = _scaled(price, min(prices), max(prices), lower_is_better=True)
        delivery_score = (
            _scaled(offer.delivery_estimate_days, min(days), max(days), lower_is_better=True) if days else 0.0
        )
        rating_score = offer.rating / 5 if offer.rating is not None else config.missing_rating_score
        total = (
            w.get("price", 0) * price_score
            + w.get("delivery", 0) * delivery_score
            + w.get("rating", 0) * rating_score
        )
        scored.append(
            ScoredOffer(
                offer=offer,
                score=round(total, 4),
                price_score=price_score,
                delivery_score=delivery_score,
                rating_score=round(rating_score, 4),
                total_price=round(price * request.quantity, 2),
            )
        )
    return sorted(scored, key=lambda s: s.score, reverse=True)


# -- 4. group ---------------------------------------------------------------------


def group_offers(scored: list[ScoredOffer]) -> list[ProductGroup]:
    """Same manufacturer part number at several suppliers becomes one row."""
    groups: dict[str, list[ScoredOffer]] = {}
    for s in scored:  # already best-first, so each group stays best-first
        key = s.offer.match_key or f"{s.offer.supplier}:{s.offer.supplier_product_id}"
        groups.setdefault(key, []).append(s)

    result = []
    for key, members in groups.items():
        cheapest = min(members, key=lambda s: s.total_price)
        result.append(
            ProductGroup(
                product_name=members[0].offer.product_name,
                match_key=members[0].offer.match_key,
                offers=members,
                cheapest_supplier=cheapest.offer.supplier,
            )
        )
    return sorted(result, key=lambda g: g.best.score, reverse=True)


# -- all together -----------------------------------------------------------------


def compare(
    request: SearchRequest,
    suppliers: list[SupplierAdapter] | None = None,
    config: ScoringConfig | None = None,
) -> ComparisonResult:
    config = config or ScoringConfig.load()
    suppliers = suppliers if suppliers is not None else default_suppliers()
    offers, statuses = search_all(request, suppliers, timeout=config.supplier_timeout_seconds)
    return rank(offers, statuses, request, config)


def rank(
    offers: list[Offer],
    statuses: list[SupplierStatus],
    request: SearchRequest,
    config: ScoringConfig,
) -> ComparisonResult:
    """Filter, score and group offers that were already fetched.

    Kept separate from the search so the UI can re-rank with new weights instantly,
    without asking the suppliers again.
    """
    kept, dropped = filter_offers(offers, request, config)
    groups = group_offers(score_offers(kept, request, config))
    return ComparisonResult(request=request, groups=groups, dropped=dropped, suppliers=statuses)
