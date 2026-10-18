"""Run the comparison engine from the command line (no LLM).

Usage:
    python tools/compare.py "27 monitor" --qty 2 --max-price 450 --exclude arm mount gaming
    python tools/compare.py "usb-c dock" --must "usb-c" --dropped
    python tools/compare.py "laptop" "notebook" --local      # skip DummyJSON (no network)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from procurement_agent.comparison import ComparisonResult, SearchRequest, compare  # noqa: E402
from procurement_agent.suppliers import NorthStarSupplier, TechSourceSupplier  # noqa: E402


def short(supplier: str) -> str:
    return supplier.split()[0]


def print_result(result: ComparisonResult, show_dropped: bool) -> None:
    print("Suppliers:")
    for s in result.suppliers:
        status = f"{s.offers_found} found" if s.ok else f"FAILED ({s.error})"
        print(f"  {s.supplier:<26} {status}")
    print()

    if result.found_nothing:
        print("No suitable product found.")
    else:
        print(f"{'#':>2}  {'score':>5}  {'product':<46} offers (* = cheapest)")
        print("-" * 110)
        for i, group in enumerate(result.groups, start=1):
            offers = "   ".join(
                f"{'*' if s.offer.supplier == group.cheapest_supplier and len(group.offers) > 1 else ' '}"
                f"{short(s.offer.supplier)} ${s.offer.price:,.2f} {s.offer.delivery_estimate_days}d"
                for s in group.offers
            )
            print(f"{i:>2}  {group.best.score:>5.2f}  {group.product_name[:46]:<46} {offers}")

    print(f"\n{len(result.groups)} product(s) kept, {len(result.dropped)} offer(s) dropped")
    if show_dropped and result.dropped:
        print("\nDropped:")
        for d in result.dropped:
            print(f"  {short(d.offer.supplier):<10} {d.offer.product_name[:44]:<44} {d.reason}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="+", help="one or more keyword searches")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--max-price", type=float, help="budget per unit, USD")
    ap.add_argument("--must", nargs="*", default=[], help="words every offer must mention")
    ap.add_argument("--exclude", nargs="*", default=[], help="words that rule an offer out")
    ap.add_argument("--dropped", action="store_true", help="list dropped offers and why")
    ap.add_argument("--local", action="store_true", help="only the two mock suppliers")
    args = ap.parse_args()

    request = SearchRequest(
        search_terms=args.terms,
        quantity=args.qty,
        max_unit_price=args.max_price,
        must_have=args.must,
        exclude=args.exclude,
    )
    suppliers = [NorthStarSupplier(), TechSourceSupplier()] if args.local else None
    print_result(compare(request, suppliers=suppliers), args.dropped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
