# Procurement Agent (prototype)

An AI assistant for buying standard office and IT equipment. An employee describes what they need
in their own words; the agent searches three suppliers, compares price, delivery and rating,
recommends one offer with its reasoning, and drafts a purchase request for approval. Nothing is
ever ordered automatically: a person confirms every request.

The brief is in `full_requirements_doc.txt`. A walkthrough for presenting it is in
[`docs/demo-script.md`](docs/demo-script.md).

## Quick start

Requires Python 3.11+ and AWS credentials with access to Claude on Amazon Bedrock.

```
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env          # then add your AWS keys
venv/bin/pytest -q            # offline tests, no AWS calls
venv/bin/streamlit run app.py # opens http://localhost:8501
```

`.env` holds `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (only for temporary
credentials), `AWS_REGION` and `BEDROCK_MODEL_ID` (default `anthropic.claude-sonnet-5`). It is
git-ignored; no keys are in the repo.

## Using the app

- **Ask** in the chat box, or click one of the example requests.
- **Read the result:** what the agent understood, the recommendation with caveats, which suppliers
  answered, the comparison table (lowest price in bold) and a tab listing every dropped offer and why.
- **Tune the ranking** with the sidebar sliders (price, delivery speed, rating, plus filter limits).
  The table re-ranks instantly; **Refresh recommendation** asks Claude to re-explain the new order.
  **Save** writes the values to `config/scoring.json`, **Reset** goes back to that file.
- **Request purchase** on any row opens a confirmation dialog (quantity, justification, an explicit
  "nothing is ordered" checkbox). Confirming creates a structured draft request and an email to
  `procurement@yourcompany.com` with a copy button. Requester name, department and cost center
  come from the sidebar.

## Architecture

```
Employee ──► Streamlit app (app.py, ui/)
                │
                ▼
  1. Understand ── Claude (llm.py) ──────────► SearchRequest
                │      plain English in, fixed fields out (structured output)
                ▼
  2. Search ────── NorthStar  TechSource  DummyJSON      in parallel, 8 s timeout each
                │      (JSON file)  (JSON file)  (REST API)
                ▼
  3. Normalize ─── one adapter per supplier ─► Offer (models.py)
                ▼
  4. Filter ────── comparison.py: drop with a recorded reason
  5. Score ─────── weighted price / delivery / rating from config/scoring.json
  6. Group ─────── same manufacturer part number = one product row
                ▼
  7. Explain ───── Claude (recommend.py) ────► reasoning + caveats, numbers checked
                ▼
  8. Confirm ───── human ──► PurchaseRequest + email draft (purchase_request.py)
```

**Design rule:** Claude handles language, code handles decisions. The model reads the request
(step 1) and explains the result (step 7). Every search, filter, number, ranking and the purchase
gate is ordinary, testable Python.

### How the agent decides what to do

It is a **fixed pipeline**, not a free-running agent loop: the same eight steps run in the same order
for every request. Claude is called exactly twice and can't trigger searches, change the ranking or
place orders.

1. **Understand (Claude).** Claude turns the sentence into a `SearchRequest`: 1 to 3 keyword
   searches, quantity, budget per unit, must-have words and exclusions. The reply is forced into
   that schema, then validated (quantity capped at 500, empty or negative values discarded).
   Messages that aren't purchase requests, including attempts to override the instructions,
   come back as "not a product request" and nothing is searched.
2. **Search (code).** All three suppliers are queried at once with a timeout. A failed or slow
   supplier is reported in the UI; the others still return.
3. **Normalize (code).** Each adapter maps its supplier's format to the shared `Offer` model
   (`suppliers/northstar.py` and `techsource.py` show the field mappings).
4. **Filter (code).** An offer is dropped, with the reason kept, if it doesn't match the search,
   lacks a must-have word, mentions an excluded word, has no price, is out of stock, backordered or
   of unknown availability, has too little stock or a minimum order above the quantity, is over
   budget, or costs under 30% of the typical price for the search (suspicious, needs review).
5. **Score (code).** Price, delivery speed and rating are each scaled 0 to 1 across the remaining
   offers and weighted by `config/scoring.json` (currently 0.60 / 0.10 / 0.30). A missing rating
   counts as 0.5.
6. **Group (code).** Offers with the same manufacturer part number (after removing case, spaces
   and dashes) become one row, so the same monitor at two suppliers is compared side by side.
7. **Explain (Claude).** The recommendation is always the top-scored row and the runner-up row 2;
   code decides that. Claude sees only the top 5 rows and a count of dropped offers by reason, and
   writes 2 to 3 sentences plus caveats (low stock, short warranty, cheaper elsewhere). Every dollar
   amount and day count it writes is checked against that data; anything that doesn't match is
   shown as a warning, not as fact. With no results, it explains why and suggests a rephrase.
8. **Confirm (human).** The purchase request is a draft for approval. No API is called and no
   email is sent.

### Components

```
app.py                  Streamlit entry point
.streamlit/config.toml  Theme
config/scoring.json     Ranking weights and filter limits (edit here or save from the app)
src/procurement_agent/
  models.py             Offer: the one shape every supplier is converted to
  suppliers/            One adapter per supplier, all implementing SupplierAdapter (base.py)
    local_file.py       Shared loading and keyword search for the JSON-file suppliers
    northstar.py, techsource.py, dummyjson.py
  comparison.py         Search all suppliers, filter with reasons, score, group
  llm.py                Claude on Bedrock: request -> SearchRequest
  recommend.py          Claude: top rows -> reasoning and caveats, with the number check
  purchase_request.py   Chosen offer -> structured purchase request and email draft
  ui/                   Streamlit: session state, sidebar, chat turns, results, purchase dialog, styles
setup/generate_mock_suppliers.py   Builds the two mock supplier files
data/suppliers/         The generated mock data
tools/                  Command-line helpers (below)
tests/                  89 offline tests: adapters, engine, Claude steps (faked), purchase request, app
```

## Data sources

| Supplier | Source | Notes |
| --- | --- | --- |
| NorthStar Office Supply | `data/suppliers/northstar_office.json`, 100 items | Flat layout. Publishes ship time only, so delivery = ship time + assumed transit for the shipping method |
| TechSource Supply Co. | `data/suppliers/techsource.json`, 100 items | Nested layout, inconsistent names and part-number formatting, backorders |
| DummyJSON | Public REST API, `https://dummyjson.com/products` | Real HTTP calls; consumer goods (laptops, phones, tablets), no monitors or docks |

The two mock suppliers are generated from one catalog of 154 office and IT products; 46 products
are sold by both under different names, part-number formats and prices. Edge cases are built in
on purpose:

| Case | NorthStar | TechSource |
| --- | --- | --- |
| Missing price | 4 "Call for pricing" | 2 "on request", 1 with a missing amount |
| Unavailable | 23 out of stock | 7 backordered (3 to 8 weeks), 2 discontinued |
| Same product at both suppliers | 46 | 46 |
| Near misses | 24", 32", 34" and gaming monitors, USB-A-only docks | same |
| Suspicious price | one 27" monitor at $27.99 | none |
| Missing rating | 5 | 19 |
| Minimum order above 1 | 3 | 3 |
| Long lead time | 2 items shipping in 45 days | the backorders |

Rebuild the files with `venv/bin/python setup/generate_mock_suppliers.py` (fixed seed, same output).

**Why mock data plus one public API:** real retailers' terms usually forbid scraping, and scraping
is slow and fragile in a live demo. The mock files give realistic, repeatable edge cases;
DummyJSON proves the same adapter pattern works over real HTTP, with a real network failure mode.
In production each adapter would call a supplier's catalog API or a punch-out/cXML feed instead.

## Command-line tools

```
# Full pipeline without the UI (needs .env)
venv/bin/python tools/ask.py "I need an alphanumeric typing pad"
venv/bin/python tools/ask.py "Two 27-inch office monitors, under \$450 each" --dropped

# Comparison engine only, no Claude
venv/bin/python tools/compare.py "27 monitor" --qty 2 --max-price 450 --exclude arm mount --dropped
venv/bin/python tools/compare.py "usb-c dock" --local          # mock suppliers only, no network

# Raw supplier search, no filtering
venv/bin/python tools/search_suppliers.py "usb-c dock"
venv/bin/python tools/search_suppliers.py "laptop" --supplier all
venv/bin/python tools/search_dummyjson.py --id 78 --json
```

## Trade-offs

| Choice | Why | Cost |
| --- | --- | --- |
| Fixed pipeline over an autonomous agent loop | Same steps every run, easy to explain, test and audit; predictable in a demo | Can't decide on its own to retry with broader terms or ask follow-up questions |
| LLM for language only | Numbers, filters and ranking are reproducible and unit-tested; the model can't invent a price | Ranking is only as smart as the scoring formula |
| Structured outputs | Claude's reply always parses into a validated object | Less free-form flexibility |
| Keyword search | Simple and transparent; Claude bridges the user's words to catalog words | Whole-word matching misses some synonyms (for example "speaker" vs "speakerphone") |
| Mock data over live shops | Repeatable edge cases, no scraping or terms-of-service issues | Not live prices or stock |
| Draft request over real ordering | Safe by design; shows where approval sits | Approval routing is not implemented |

## Known limitations

- The suspicious-price check compares against other results in the same search, so genuinely cheap
  items (a $21 keyboard among $90 ones) are also held for review, and a search full of accessories
  has no meaningful baseline.
- DummyJSON gives many products a minimum order of 2 to 5, so at quantity 1 several are dropped.
- Claude can still pick a search word the catalog doesn't use, or add a must-have the user only
  implied; the dropped-offers tab shows when that happened.
- Sessions live in memory: chat history and draft requests are lost when the app restarts.

## Hardening for an enterprise customer

- **Authentication and roles:** single sign-on (for example Entra ID) in front of the app; requester
  name, department and cost center taken from the identity provider instead of typed in.
- **Approvals:** submit the request to a workflow (Power Automate, ServiceNow, Jira or the ERP)
  with routing by amount and cost center, and budget checks, instead of an email draft.
- **Audit trail:** store every request, the `SearchRequest`, the offers seen, each drop reason,
  the scores, the model's text and the final decision, with who approved what and when.
- **Suppliers:** contracted catalog APIs or punch-out (cXML/OCI) with negotiated prices, real stock
  and SLAs; an approved-supplier list; caching and rate limits.
- **Secrets and network:** credentials in a secrets manager or an IAM role, not `.env`; Bedrock over
  a private endpoint; least-privilege access to the model.
- **Data privacy:** only product requests and supplier offers go to the model, no personal data in
  prompts (the requester's details stay in the app); pin the Bedrock region to meet data-residency
  needs and confirm the account's data-use, retention and logging settings.
- **Responsible AI:** keep the model away from decisions (already the case); evaluate the two
  prompts against a test set of real requests; monitor refusals, unverified numbers and
  "nothing found" rates; human confirmation for every purchase.
- **Operations:** containerize, add health checks, structured logs and tracing per request, retries
  with backoff for suppliers, and alerts when a supplier fails repeatedly.
