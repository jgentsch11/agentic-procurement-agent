"""Rendering one search result: understanding, recommendation, table, dropped offers."""

from __future__ import annotations

import time
from collections.abc import Iterator

import pandas as pd
import streamlit as st

from procurement_agent.comparison import ComparisonResult, ScoredOffer, SearchRequest
from procurement_agent.llm import RequestUnderstanding
from procurement_agent.recommend import Recommendation

HIGHLIGHT = "font-weight: 700;"


def short_supplier(name: str) -> str:
    return name.replace(" Office Supply", "").replace(" Supply Co.", "")


def md(text: str) -> str:
    """Escape dollar signs: Streamlit markdown treats text between two "$" as LaTeX math."""
    return text.replace("$", "\\$")


def money(value: float | None) -> str:
    return f"${value:,.2f}" if value is not None else "quote"


def word_stream(text: str, delay: float = 0.018) -> Iterator[str]:
    """Feed already-checked text to st.write_stream a word at a time."""
    for word in md(text).split(" "):
        yield word + " "
        time.sleep(delay)


# -- what the agent understood -----------------------------------------------------


def render_understanding(understanding: RequestUnderstanding, request: SearchRequest) -> None:
    with st.container(border=True):
        st.markdown(f"**What I understood:** {md(understanding.summary)}")
        with st.container(horizontal=True, gap="small"):
            for term in request.search_terms:
                st.badge(term, icon=":material/search:", color="primary")
            st.badge(f"Qty {request.quantity}", icon=":material/inventory_2:", color="gray")
            if request.max_unit_price:
                st.badge(f"Up to {money(request.max_unit_price)} each", icon=":material/payments:", color="gray")
            for m in request.must_have:
                st.badge(f"Must have: {m}", icon=":material/check:", color="green")
            for x in request.exclude:
                st.badge(f"Exclude: {x}", icon=":material/block:", color="orange")


def render_supplier_status(result: ComparisonResult) -> None:
    with st.container(horizontal=True, gap="small"):
        for s in result.suppliers:
            if s.ok:
                st.badge(f"{short_supplier(s.supplier)}: {s.offers_found} found", icon=":material/check_circle:", color="green")
            else:
                st.badge(f"{short_supplier(s.supplier)}: unavailable", icon=":material/error:", color="red", help=s.error)


# -- recommendation ---------------------------------------------------------------


def render_recommendation(rec: Recommendation, stream: bool) -> None:
    with st.container(border=True):
        if rec.top:
            best = rec.top.best
            st.markdown("#### ✅ Recommended")
            cols = st.columns([3, 1.2, 1, 1])
            cols[0].markdown(f"**{md(rec.top.product_name)}**  \n{best.offer.supplier}")
            cols[1].metric("Total", money(best.total_price))
            cols[2].metric("Delivery", f"{best.offer.delivery_estimate_days}d" if best.offer.delivery_estimate_days else "-")
            cols[3].metric("Rating", f"{best.offer.rating:.1f}" if best.offer.rating is not None else "-")
        else:
            st.markdown("#### No suitable product found")

        if stream:
            st.write_stream(word_stream(rec.reasoning))
        else:
            st.markdown(md(rec.reasoning))

        if rec.caveats:
            title = "Before you buy" if rec.top else "Try instead"
            with st.container(border=False):
                st.markdown(f"**{title}**")
                for c in rec.caveats:
                    st.markdown(f"- {md(c)}")
        if rec.unverified_numbers:
            st.warning(
                md(f"Check: {', '.join(rec.unverified_numbers)} could not be matched to the supplier data."),
                icon=":material/fact_check:",
            )
        if rec.runner_up:
            ru = rec.runner_up.best
            st.caption(md(f"Runner-up: {rec.runner_up.product_name} from {ru.offer.supplier}, {money(ru.total_price)} total"))


# -- comparison table -------------------------------------------------------------


def offer_rows(result: ComparisonResult) -> list[tuple[int, ScoredOffer, bool]]:
    """(rank, offer, is_lowest_price_overall) for every kept offer, in table order.

    Ties all count as the lowest price.
    """
    offers = [(rank, s) for rank, group in enumerate(result.groups, start=1) for s in group.offers]
    if not offers:
        return []
    lowest = min(s.total_price for _, s in offers)
    return [(rank, s, abs(s.total_price - lowest) < 0.005) for rank, s in offers]


COLUMN_ORDER = [
    "#", "Product", "Supplier", "Score", "Rating", "Unit price", "Total",
    "Delivery (days)", "Availability", "Best price",
]


def comparison_frame(result: ComparisonResult) -> pd.DataFrame:
    records = []
    for rank, s, cheapest in offer_rows(result):
        o = s.offer
        records.append(
            {
                "#": rank,
                "Product": o.product_name,
                "Supplier": short_supplier(o.supplier),
                "Unit price": o.effective_price if o.effective_price is not None else o.price,
                "Total": s.total_price,
                "Delivery (days)": o.delivery_estimate_days,
                "Availability": o.availability_text or o.availability.value,
                "Rating": o.rating,
                "Score": s.score,
                "Best price": "★ lowest price" if cheapest else "",
            }
        )
    return pd.DataFrame.from_records(records)


def render_comparison_table(result: ComparisonResult, key: str) -> None:
    df = comparison_frame(result)[COLUMN_ORDER]
    styled = df.style.apply(
        lambda row: [HIGHLIGHT if row["Best price"] else "" for _ in row], axis=1
    )
    st.dataframe(
        styled,
        key=key,
        hide_index=True,
        width="stretch",
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Product": st.column_config.TextColumn(width="large"),
            "Unit price": st.column_config.NumberColumn(format="$%.2f"),
            "Total": st.column_config.NumberColumn(format="$%.2f"),
            "Rating": st.column_config.NumberColumn(format="%.1f ⭐"),
            "Score": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )
    st.caption("The lowest-priced offer is in bold. The same product at two suppliers shares a rank.")


def render_dropped(result: ComparisonResult, key: str) -> None:
    if not result.dropped:
        st.caption("Nothing was dropped.")
        return
    df = pd.DataFrame.from_records(
        {
            "Product": d.offer.product_name,
            "Supplier": short_supplier(d.offer.supplier),
            "Price": d.offer.price,
            "Reason": d.reason,
        }
        for d in result.dropped
    )
    st.dataframe(
        df, key=key, hide_index=True, width="stretch",
        column_config={"Price": st.column_config.NumberColumn(format="$%.2f"),
                       "Reason": st.column_config.TextColumn(width="large")},
    )
