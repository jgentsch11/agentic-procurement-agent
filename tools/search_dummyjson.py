"""Query DummyJSON and print normalized offers.

Usage:
    python tools/search_dummyjson.py "laptop"
    python tools/search_dummyjson.py "laptop" --limit 5 --json
    python tools/search_dummyjson.py --category laptops
    python tools/search_dummyjson.py --id 78
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from procurement_agent.models import Offer  # noqa: E402
from procurement_agent.suppliers import DummyJSONSupplier, SupplierError  # noqa: E402

COLUMNS = [
    ("id", lambda o: o.supplier_product_id, 4),
    ("product_name", lambda o: o.product_name, 38),
    ("supplier", lambda o: o.supplier, 9),
    ("brand", lambda o: o.brand or "-", 10),
    ("category", lambda o: o.category or "-", 18),
    ("sku", lambda o: o.sku or "-", 16),
    ("price", lambda o: f"{o.price:.2f}" if o.price is not None else "quote", 9),
    ("availability", lambda o: o.availability_text or o.availability.value, 12),
    ("stock", lambda o: str(o.stock_quantity) if o.stock_quantity is not None else "-", 5),
    ("delivery", lambda o: f"{o.delivery_estimate_days}d" if o.delivery_estimate_days else "-", 8),
    ("rating", lambda o: f"{o.rating:.2f}" if o.rating is not None else "-", 6),
    ("return", lambda o: o.return_policy or "-", 22),
]


def print_table(offers: list[Offer]) -> None:
    header = " | ".join(name.ljust(width)[:width] for name, _, width in COLUMNS)
    print(header)
    print("-" * len(header))
    for o in offers:
        print(" | ".join(str(fn(o)).ljust(width)[:width] for _, fn, width in COLUMNS))
    print(f"\n{len(offers)} offer(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="free-text search")
    ap.add_argument("--category", help="browse a category slug instead of searching")
    ap.add_argument("--id", help="fetch a single product by ID")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json", action="store_true", help="emit normalized JSON instead of a table")
    args = ap.parse_args()

    supplier = DummyJSONSupplier()
    try:
        if args.id:
            offer = supplier.get(args.id)
            offers = [offer] if offer else []
        elif args.category:
            offers = supplier.browse_category(args.category, limit=args.limit)
        elif args.query:
            offers = supplier.search(args.query, limit=args.limit)
        else:
            ap.error("provide a query, --category, or --id")
    except SupplierError as exc:
        print(f"supplier error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([o.model_dump(mode="json") for o in offers], indent=2))
    else:
        print_table(offers)
        if not offers:
            print("No products matched. (DummyJSON has no monitors/docking stations; try 'laptop', 'tablet', 'phone'.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
