"""Plain-English request in, comparison out: Claude reads the request, code does the rest.

Usage:
    python tools/ask.py "I need an alphanumeric typing pad"
    python tools/ask.py "Two 27-inch office monitors, under \\$450 each" --dropped
    python tools/ask.py "5 webcams, total budget \\$500" --understand-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from compare import print_result  # noqa: E402

from procurement_agent.comparison import compare  # noqa: E402
from procurement_agent.llm import LLMError, understand_request  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("request", help="what you want to buy, in your own words")
    ap.add_argument("--understand-only", action="store_true", help="stop after Claude reads the request")
    ap.add_argument("--dropped", action="store_true", help="list dropped offers and why")
    args = ap.parse_args()

    try:
        understanding = understand_request(args.request)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Understood: {understanding.summary}")
    try:
        request = understanding.to_search_request()
    except ValueError:
        print("Nothing to search for. Try describing the office or IT item you need.")
        return 1

    print(
        f"Search: {', '.join(request.search_terms)} | qty {request.quantity}"
        f" | budget {f'${request.max_unit_price:,.2f}/unit' if request.max_unit_price else 'none'}"
        f" | must have: {', '.join(request.must_have) or '-'} | exclude: {', '.join(request.exclude) or '-'}\n"
    )
    if not args.understand_only:
        print_result(compare(request), args.dropped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
