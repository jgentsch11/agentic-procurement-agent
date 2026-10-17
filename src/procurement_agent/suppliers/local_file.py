"""Shared base for suppliers whose catalog is a local JSON file.

Subclasses say where the records live in the file, how to turn one record into
an `Offer`, and which text to search. Loading, keyword search and lookup by ID
are the same for every file-based supplier, so they live here.
"""

from __future__ import annotations

import json
import re
from abc import abstractmethod
from pathlib import Path
from typing import Any

from procurement_agent.models import Offer
from procurement_agent.suppliers.base import SupplierAdapter, SupplierError

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "suppliers"

_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _word_matches(word: str, haystack: set[str]) -> bool:
    """'monitors' matches 'monitor' and vice versa."""
    if word in haystack:
        return True
    if word.endswith("s") and word[:-1] in haystack:
        return True
    return f"{word}s" in haystack


class LocalFileSupplier(SupplierAdapter):
    default_file: str

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DATA_DIR / self.default_file
        self._offers: list[Offer] | None = None
        self._index: list[set[str]] = []

    # -- subclass hooks -----------------------------------------------------

    @abstractmethod
    def records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull the list of product records out of the loaded file."""

    @abstractmethod
    def to_offer(self, raw: dict[str, Any]) -> Offer:
        """Translate one raw record into the canonical `Offer`."""

    @abstractmethod
    def search_text(self, raw: dict[str, Any]) -> str:
        """Text a keyword search should look at for this record."""

    # -- public API ---------------------------------------------------------

    def search(self, query: str, *, limit: int = 20) -> list[Offer]:
        """Every query word must appear in the record's search text."""
        words = _words(query)
        if not words:
            return []
        offers = self.all()
        hits = [
            offer
            for offer, haystack in zip(offers, self._index)
            if all(_word_matches(w, haystack) for w in words)
        ]
        return hits[:limit]

    def get(self, product_id: str) -> Offer | None:
        return next((o for o in self.all() if o.supplier_product_id == product_id), None)

    def all(self) -> list[Offer]:
        if self._offers is None:
            self._load()
        return self._offers

    # -- internals ----------------------------------------------------------

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text())
            raws = self.records(payload)
        except FileNotFoundError as exc:
            raise SupplierError(self.name, f"catalog file not found: {self.path}") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise SupplierError(self.name, f"malformed catalog file: {self.path}") from exc
        self._offers = [self.to_offer(r) for r in raws]
        self._index = [set(_words(self.search_text(r))) for r in raws]
