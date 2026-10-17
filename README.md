# Procurement Agent (prototype)

An agentic procurement assistant. It takes a product request, queries three supplier sources,
compares the offers, recommends one, and prepares a purchase request that a human must confirm.

The full brief is in `full_requirements_doc.txt`.

## Tech stack

- Python, with Amazon Bedrock as the LLM
- Pydantic AI for the agent layer
- Streamlit for the chat input, comparison table and confirm button
- `.env` for keys (copy `.env.example`; no keys in the repo)

## Folder layout

```
setup/                  One-time setup. Builds the mock supplier data.
  generate_mock_suppliers.py
data/suppliers/         Generated mock data (output of setup/)
  northstar_office.json
  techsource.json
src/procurement_agent/  The agent program
  models.py             Offer: the one shape every supplier is converted to
  suppliers/            One adapter per supplier
    local_file.py       Shared loading and keyword search for the JSON-file suppliers
    northstar.py, techsource.py, dummyjson.py
tools/                  Manual helpers for poking at a supplier
  search_suppliers.py   Search NorthStar and TechSource (or all three)
  search_dummyjson.py
tests/
```

## Setup

```
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python setup/generate_mock_suppliers.py   # only needed to rebuild data/suppliers
venv/bin/pytest -q
```

Search the two mock suppliers (no network needed):

```
venv/bin/python tools/search_suppliers.py "usb-c dock"
venv/bin/python tools/search_suppliers.py "27 monitor" --supplier techsource
venv/bin/python tools/search_suppliers.py "laptop" --supplier all     # adds DummyJSON
```

Try the DummyJSON supplier on its own:

```
venv/bin/python tools/search_dummyjson.py "laptop" --limit 5
venv/bin/python tools/search_dummyjson.py --category laptops
venv/bin/python tools/search_dummyjson.py --id 78 --json
```

## Suppliers

All prices are in US dollars.

| Supplier | Source | Status |
| --- | --- | --- |
| DummyJSON | Public read-only REST API (`https://dummyjson.com/products`) | adapter built |
| NorthStar Office Supply | `data/suppliers/northstar_office.json` (100 items) | adapter built |
| TechSource Supply Co. | `data/suppliers/techsource.json` (100 items) | adapter built |

Every adapter implements `SupplierAdapter` (`suppliers/base.py`) and returns `Offer` objects
(`models.py`), so the rest of the program never sees a supplier-specific format.

The two mock suppliers come from one shared catalog of 154 office/IT products. 46 products
appear at both suppliers with different names, part-number formatting and prices, so the agent
can show the same item side by side and rank the cheaper offer higher. Neither supplier lists
the same product twice. Their JSON layouts are
deliberately different (NorthStar is flat, TechSource is nested) so the adapters have real
conversion work to do.

## How it works, step by step

Example request: *"I need a 27-inch monitor suitable for office work, two of them, under $450 each."*

1. **Understand the request (LLM).** The model turns the text into a structured object:
   category, quantity, budget, must-haves, nice-to-haves, exclusions and search terms. If the
   request is too vague ("I need a monitor"), it asks a clarifying question instead of searching.
2. **Search all three suppliers (code).** One `search_products` tool queries the three adapters
   in parallel with a timeout. If one supplier is down, the others still return and the UI says so.
3. **Normalize (code).** Each supplier's raw format is converted to the common `Offer` shape.
4. **Filter, with reasons (code).** Offers are dropped for wrong size, over budget, out of stock,
   no price (shown as "quote required"), order minimum too high, or a suspiciously low price.
   Each drop reason is kept for the audit log.
5. **Score (code).** Remaining offers are ranked by
   `0.40 × price + 0.30 × delivery speed + 0.30 × rating` (each scaled 0 to 1).
   Weights live in a config file so procurement can change them without touching a prompt.
6. **Recommend (LLM).** The model sees only the top ~5 scored offers and writes a short
   recommendation, a runner-up and any caveats. It may only cite values present in that data.
7. **Show results (Streamlit).** What the agent understood, the comparison table, and the
   recommendation.
8. **Human confirms.** A "Request purchase" button opens a confirmation with quantity, price,
   total and supplier. Nothing is bought; it only shows where the human approval step sits.

Design rule: the LLM handles language (understanding and explaining). Code handles every number,
filter, ranking and the purchase gate.

## Edge cases built into the mock data

| Case | NorthStar | TechSource |
| --- | --- | --- |
| Missing price | 4 items "Call for pricing" | 2 "on request", 1 with a missing amount |
| Unavailable | 23 out of stock | backorders (3 to 8 weeks) and discontinued items |
| Same product at both suppliers | 46 products | 46 products |
| Near misses | 24"/32"/34" and gaming monitors, USB-A-only docks | same catalog |
| Suspicious price | one 27" monitor at $27.99 | none |
| Missing rating | 5 items | 19 items |
| Order minimum above 1 | 3 items | 3 items |
| Long lead time | 2 items shipping in 45 days | backorder items |

## DummyJSON caveats

- No API key, no rate-limit contract and no SLA: it is a prototyping source, not a trusted supplier.
- Writes are simulated and never saved, so purchase requests are queued locally, not sent there.
- It has no monitors or docking stations, and its search is a loose text match (searching
  "monitor" returns a kitchen pot), so the program's own filter must reject off-category results.
