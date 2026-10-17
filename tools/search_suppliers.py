"""Search one or all suppliers and print normalized offers.

Usage:
    python tools/search_suppliers.py "usb-c dock"
    python tools/search_suppliers.py "27 monitor" --supplier techsource
    python tools/search_suppliers.py --supplier northstar --id NS-100007 --json
    python tools/search_suppliers.py "laptop" --supplier all      # includes DummyJSON (network)

By default only the two local mock suppliers are searched, so no network is needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from procurement_agent.models import Offer  # noqa: E402
from procurement_agent.suppliers import (  # noqa: E402
    DummyJSONSupplier,
    NorthStarSupplier,
    SupplierError,
    TechSourceSupplier,
)

SUPPLIERS = {
    "northstar": NorthStarSupplier,
    "techsource": TechSourceSupplier,
    "dummyjson": DummyJSONSupplier,
}
CHOICES = {
    "local": ["northstar", "techsource"],
    "all": ["northstar", "techsource", "dummyjson"],
    **{k: [k] for k in SUPPLIERS},
}

COLUMNS = [
    ("supplier", lambda o: o.supplier, 12),
    ("id", lambda o: o.supplier_product_id, 9),
    ("product_name", lambda o: o.product_name, 40),
    ("mpn", lambda o: o.manufacturer_part_number or "-", 14),
    ("price", lambda o: f"{o.price:.2f}" if o.price is not None else "quote", 8),
    ("availability", lambda o: o.availability_text or o.availability.value, 22),
    ("delivery", lambda o: f"{o.delivery_estimate_days}d" if o.delivery_estimate_days else "-", 8),
    ("rating", lambda o: f"{o.rating:.2f}" if o.rating is not None else "-", 6),
    ("min", lambda o: str(o.minimum_order_quantity), 3),
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
    ap.add_argument("query", nargs="?", help="keyword search")
    ap.add_argument("--supplier", choices=sorted(CHOICES), default="local")
    ap.add_argument("--id", help="fetch a single product by the supplier's own ID")
    ap.add_argument("--limit", type=int, default=20, help="max results per supplier")
    ap.add_argument("--json", action="store_true", help="emit normalized JSON instead of a table")
    args = ap.parse_args()
    if not args.query and not args.id:
        ap.error("provide a query or --id")

    offers: list[Offer] = []
    for key in CHOICES[args.supplier]:
        supplier = SUPPLIERS[key]()
        try:
            if args.id:
                offer = supplier.get(args.id)
                offers += [offer] if offer else []
            else:
                offers += supplier.search(args.query, limit=args.limit)
        except SupplierError as exc:
            print(f"supplier error: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps([o.model_dump(mode="json") for o in offers], indent=2))
    else:
        print_table(offers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
