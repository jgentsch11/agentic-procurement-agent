"""Chat turns: run the pipeline for a new request and render every turn."""

from __future__ import annotations

import logging

import streamlit as st

from procurement_agent.comparison import ScoringConfig, default_suppliers, search_all
from procurement_agent.llm import LLMError, understand_request
from procurement_agent.recommend import recommend
from procurement_agent.ui.purchase_dialog import dialog_target, open_dialog, purchase_dialog
from procurement_agent.ui.results import (
    md,
    money,
    offer_rows,
    render_comparison_table,
    render_dropped,
    render_recommendation,
    render_supplier_status,
    render_understanding,
    short_supplier,
)
from procurement_agent.ui.state import Turn

log = logging.getLogger(__name__)

USER_AVATAR = "🧑‍💼"
AGENT_AVATAR = "🛒"

EXAMPLES = [
    "Two 27-inch monitors for office work, under $450 each",
    "A docking station for USB-C laptops",
    "I need an alphanumeric typing pad",
    "5 webcams for the meeting rooms, total budget $600",
]


# -- running the pipeline ----------------------------------------------------------


def run_turn(turn: Turn, config: ScoringConfig) -> None:
    """Fill `turn` in place. Each step reports progress in a status box."""
    with st.status("Reading your request…", expanded=False) as status:
        try:
            turn.understanding = understand_request(turn.user_text)
            try:
                turn.request = turn.understanding.to_search_request()
            except ValueError:
                turn.kind = "not_product"
                turn.message = turn.understanding.summary
                status.update(label="Not a purchase request", state="complete")
                return

            status.update(label="Searching NorthStar, TechSource and DummyJSON…")
            turn.offers, turn.statuses = search_all(
                turn.request, default_suppliers(), timeout=config.supplier_timeout_seconds
            )
            result = turn.result(config)
            found = sum(s.offers_found for s in result.suppliers)
            status.update(label=f"Ranking {found} offers…")

            status.update(label="Writing the recommendation…")
            try:
                turn.recommendation = recommend(result, turn.user_text)
                turn.recommendation_config = config.model_dump()
            except LLMError as exc:
                turn.recommendation_error = str(exc)
            turn.kind = "results"
            status.update(label=f"Compared {found} offers from {len(result.suppliers)} suppliers", state="complete")
        except LLMError as exc:
            turn.kind = "error"
            turn.message = str(exc)
            status.update(label="Could not reach Claude", state="error")
        except Exception as exc:  # keep the chat usable whatever went wrong
            log.exception("Turn failed")
            turn.kind = "error"
            turn.message = f"Something went wrong: {exc}"
            status.update(label="Something went wrong", state="error")


def refresh_recommendation(turn: Turn, config: ScoringConfig) -> None:
    result = turn.result(config)
    try:
        with st.spinner("Updating the recommendation…"):
            turn.recommendation = recommend(result, turn.user_text)
        turn.recommendation_config = config.model_dump()
        turn.recommendation_error = None
        turn.streamed = False
    except LLMError as exc:
        turn.recommendation_error = str(exc)


# -- rendering --------------------------------------------------------------------


def render_turn(turn: Turn, config: ScoringConfig) -> None:
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(md(turn.user_text))

    with st.chat_message("assistant", avatar=AGENT_AVATAR):
        if turn.kind == "error":
            st.error(md(turn.message), icon=":material/error:")
            return
        if turn.kind == "not_product":
            st.info(
                f"{md(turn.message)}\n\nDescribe the office or IT item you need, for example *a webcam for video calls*.",
                icon=":material/help:",
            )
            return
        if turn.kind != "results":
            return

        result = turn.result(config)
        render_understanding(turn.understanding, turn.request)

        stale = turn.recommendation_is_stale(config)
        if stale:
            with st.container(border=True):
                cols = st.columns([4, 1.4], vertical_alignment="center")
                cols[0].markdown(
                    ":material/sync_problem: The scoring changed since this recommendation was written. "
                    "The table below already uses the new weights."
                )
                if cols[1].button("Refresh recommendation", key=f"refresh_{turn.id}", icon=":material/refresh:"):
                    refresh_recommendation(turn, config)
                    st.rerun()

        if turn.recommendation:
            render_recommendation(turn.recommendation, stream=not turn.streamed)
            turn.streamed = True
        elif turn.recommendation_error:
            st.warning(f"The comparison is ready, but no recommendation was written: {turn.recommendation_error}",
                       icon=":material/warning:")

        render_supplier_status(result)
        failed = [s for s in result.suppliers if not s.ok]
        if failed:
            st.caption("Results from the other suppliers are still shown.")

        tab_table, tab_dropped = st.tabs(
            [f"Comparison ({len(result.groups)})", f"Dropped offers ({len(result.dropped)})"]
        )
        with tab_table:
            if result.groups:
                render_comparison_table(result, key=f"table_{turn.id}")
            else:
                st.caption("No offers passed the filters. See the dropped offers for the reasons.")
        with tab_dropped:
            render_dropped(result, key=f"dropped_{turn.id}")

        if result.groups:
            render_purchase_picker(turn, result)


def render_purchase_picker(turn: Turn, result) -> None:
    rows = offer_rows(result)
    labels = [
        f"#{rank} · {s.offer.product_name} · {short_supplier(s.offer.supplier)} · {money(s.total_price)}"
        for rank, s, _ in rows
    ]
    top = result.groups[0].best
    default = next(i for i, (_, s, _) in enumerate(rows) if s is top)

    with st.container(border=True, key=f"buy_panel_{turn.id}"):
        cols = st.columns([4, 1.3], vertical_alignment="bottom")
        index = cols[0].selectbox(
            "Item to request", range(len(rows)), index=default, format_func=lambda i: labels[i],
            key=f"pick_{turn.id}",
        )
        cols[1].button(
            "Request purchase", type="primary", key=f"purchase_{turn.id}", icon=":material/shopping_cart:",
            width="stretch", on_click=open_dialog, args=(turn.id, index),
        )

    target = dialog_target()
    if target and target["turn"] == turn.id and target["index"] < len(rows):
        _, choice, _ = rows[target["index"]]
        rec = turn.recommendation
        if rec and rec.top and choice is top:
            justification = rec.reasoning
        else:
            justification = "Selected by the requester from the comparison results."
        alternatives = [g.best for g in result.groups[:3]]
        purchase_dialog(turn.id, choice, turn.request.quantity, turn.user_text, justification, alternatives)


def render_welcome() -> None:
    with st.container(border=True, key="welcome"):
        st.markdown("#### What do you need to buy?")
        st.markdown(
            "Describe the office or IT equipment in your own words. I'll check three suppliers, "
            "compare price, delivery and rating, and recommend the best option. "
            "Nothing is ordered without your confirmation."
        )
        cols = st.columns(2)
        for i, example in enumerate(EXAMPLES):
            if cols[i % 2].button(example, key=f"example_{i}", icon=":material/lightbulb:", width="stretch"):
                st.session_state.pending_prompt = example
                st.rerun()
