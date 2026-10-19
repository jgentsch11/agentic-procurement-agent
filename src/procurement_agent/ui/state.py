"""Session state: chat turns, scoring sliders and requester details.

Every widget value lives in `st.session_state` under a fixed key, so reruns,
the purchase dialog and the "reset" buttons all read and write the same place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

import streamlit as st

from procurement_agent.audit import AuditLog
from procurement_agent.comparison import (
    ComparisonResult,
    ScoringConfig,
    SearchRequest,
    SupplierStatus,
    rank,
)
from procurement_agent.llm import RequestUnderstanding
from procurement_agent.models import Offer
from procurement_agent.purchase_request import PurchaseRequest, Requester
from procurement_agent.recommend import Recommendation

# Slider keys -> how they map onto ScoringConfig.
WEIGHT_KEYS = {"price": "w_price", "delivery": "w_delivery", "rating": "w_rating"}
OTHER_KEYS = {
    "missing_rating_score": "cfg_missing_rating",
    "suspicious_price_ratio": "cfg_suspicious_ratio",
    "supplier_timeout_seconds": "cfg_timeout",
}
REQUESTER_KEYS = {"name": "req_name", "department": "req_department", "cost_center": "req_cost_center"}

_turn_ids = count(1)


@dataclass
class Turn:
    """One request and everything the agent produced for it."""

    user_text: str
    id: int = field(default_factory=lambda: next(_turn_ids))
    kind: str = "pending"  # pending | results | not_product | error
    message: str = ""
    understanding: RequestUnderstanding | None = None
    request: SearchRequest | None = None
    offers: list[Offer] = field(default_factory=list)
    statuses: list[SupplierStatus] = field(default_factory=list)
    recommendation: Recommendation | None = None
    recommendation_config: dict | None = None
    recommendation_error: str | None = None
    streamed: bool = False
    audit: AuditLog = field(default_factory=AuditLog)

    def __post_init__(self) -> None:
        self.audit.request_text = self.user_text

    def result(self, config: ScoringConfig) -> ComparisonResult | None:
        """Re-rank the stored offers with the current sliders (no supplier calls)."""
        if self.request is None:
            return None
        return rank(self.offers, self.statuses, self.request, config)

    def recommendation_is_stale(self, config: ScoringConfig) -> bool:
        return self.recommendation is not None and self.recommendation_config != config.model_dump()


def _slider_defaults(config: ScoringConfig) -> dict:
    values = {key: round(config.weights.get(name, 0) * 100) for name, key in WEIGHT_KEYS.items()}
    values |= {key: getattr(config, name) for name, key in OTHER_KEYS.items()}
    return values


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("turns", [])
    ss.setdefault("drafts", [])
    ss.setdefault("pending_prompt", None)
    if "file_config" not in ss:
        try:
            ss.file_config = ScoringConfig.load()
            ss.config_load_error = None
        except Exception as exc:  # a broken config file should not stop the app
            ss.file_config = ScoringConfig()
            ss.config_load_error = str(exc)
    for key, value in _slider_defaults(ss.file_config).items():
        ss.setdefault(key, value)
    for key in REQUESTER_KEYS.values():
        ss.setdefault(key, "")


def reset_sliders(to: ScoringConfig | None = None) -> None:
    """Used as an on_click callback, so it runs before the sliders are drawn."""
    for key, value in _slider_defaults(to or st.session_state.file_config).items():
        st.session_state[key] = value


def current_config() -> ScoringConfig:
    """Build a ScoringConfig from the sliders. Weights are normalized to sum to 1."""
    ss = st.session_state
    raw = {name: float(ss[key]) for name, key in WEIGHT_KEYS.items()}
    total = sum(raw.values())
    weights = {n: round(v / total, 4) for n, v in raw.items()} if total else {n: 1 / 3 for n in raw}
    return ScoringConfig(
        weights=weights,
        missing_rating_score=float(ss[OTHER_KEYS["missing_rating_score"]]),
        suspicious_price_ratio=float(ss[OTHER_KEYS["suspicious_price_ratio"]]),
        supplier_timeout_seconds=float(ss[OTHER_KEYS["supplier_timeout_seconds"]]),
    )


def current_requester() -> Requester:
    return Requester(**{name: st.session_state[key].strip() for name, key in REQUESTER_KEYS.items()})


def find_turn(turn_id: int) -> Turn | None:
    return next((t for t in st.session_state.turns if t.id == turn_id), None)


def add_draft(pr: PurchaseRequest) -> None:
    st.session_state.drafts.append(pr)


def clear_chat() -> None:
    st.session_state.turns = []
    st.session_state.drafts = []
    st.session_state.pending_prompt = None
