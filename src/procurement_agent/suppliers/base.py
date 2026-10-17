"""Supplier adapter interface.

The orchestrator fans a single structured query out to every registered adapter.
Each adapter is responsible for talking to its own source and returning `Offer`s.
Adapters must never raise on "no results"; they raise `SupplierError` only when
the source itself failed (timeout, 5xx, malformed payload).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from procurement_agent.models import Offer


class SupplierError(RuntimeError):
    """Raised when a supplier source could not be queried."""

    def __init__(self, supplier: str, message: str):
        self.supplier = supplier
        super().__init__(f"[{supplier}] {message}")


class SupplierAdapter(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, *, limit: int = 20) -> list[Offer]:
        """Free-text search. Returns an empty list when nothing matches."""

    @abstractmethod
    def get(self, product_id: str) -> Offer | None:
        """Fetch a single product by the supplier's own ID."""
