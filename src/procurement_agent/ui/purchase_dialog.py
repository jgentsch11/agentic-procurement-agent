"""The "Request purchase" confirmation dialog and the email draft it produces.

Nothing is ordered or sent: confirming builds a structured purchase request
and a plain-text email the employee copies into their mail client.
"""

from __future__ import annotations

import streamlit as st

from procurement_agent.comparison import ScoredOffer
from procurement_agent.purchase_request import build_purchase_request, email_draft
from procurement_agent.ui import state
from procurement_agent.ui.results import money


OPEN_KEY = "open_purchase_dialog"


def open_dialog(turn_id: int, index: int) -> None:
    st.session_state[OPEN_KEY] = {"turn": turn_id, "index": index}


def close_dialog() -> None:
    st.session_state.pop(OPEN_KEY, None)


def dialog_target() -> dict | None:
    return st.session_state.get(OPEN_KEY)


# The open/closed state lives in session_state, so the dialog survives any rerun
# until the user presses Done/Cancel or dismisses it.
@st.dialog("Confirm purchase request", width="large", icon=":material/shopping_cart_checkout:", on_dismiss=close_dialog)
def purchase_dialog(
    turn_id: int,
    choice: ScoredOffer,
    quantity: int,
    original_request: str,
    justification: str,
    alternatives: list[ScoredOffer],
) -> None:
    done_key = f"draft_for_{turn_id}"
    draft = st.session_state.get(done_key)
    if draft and draft["offer_key"] == (choice.offer.supplier, choice.offer.supplier_product_id):
        _show_draft(draft["request"], done_key)
        return

    o = choice.offer
    unit = o.effective_price if o.effective_price is not None else o.price

    with st.container(border=True):
        st.markdown(f"**{o.product_name}**  \n{o.supplier} · item `{o.supplier_product_id}`")
        min_qty = max(1, o.minimum_order_quantity)
        cols = st.columns(3)
        qty = cols[0].number_input(
            "Quantity", min_value=min_qty, max_value=500, value=max(quantity, min_qty), step=1,
            key=f"dlg_qty_{turn_id}",
        )
        cols[1].metric("Unit price", money(unit))
        cols[2].metric("Total", money(unit * qty if unit is not None else None))
        if o.stock_quantity is not None and qty > o.stock_quantity:
            st.warning(f"Only {o.stock_quantity} in stock at {o.supplier}.", icon=":material/inventory:")

    requester = state.current_requester()
    if not requester.name:
        st.info("Add your name, department and cost center in the sidebar to include them.", icon=":material/badge:")

    reason = st.text_area("Justification", value=justification, key=f"dlg_reason_{turn_id}", height=110)
    confirmed = st.checkbox(
        "I understand this creates a draft request for approval. Nothing is ordered.",
        key=f"dlg_confirm_{turn_id}",
    )

    cols = st.columns([1, 1, 2])
    if cols[0].button("Create request", type="primary", key=f"dlg_create_{turn_id}", disabled=not confirmed, icon=":material/check:"):
        try:
            pr = build_purchase_request(choice, int(qty), requester, original_request, reason, alternatives)
        except ValueError as exc:
            st.error(str(exc))
            return
        state.add_draft(pr)
        st.session_state[done_key] = {"offer_key": (o.supplier, o.supplier_product_id), "request": pr}
        st.rerun()
    if cols[1].button("Cancel", key=f"dlg_cancel_{turn_id}"):
        close_dialog()
        st.rerun()


def _show_draft(pr, done_key: str) -> None:
    st.success(f"Draft request **{pr.request_id}** created. Copy the email below into your mail client.", icon=":material/mark_email_read:")
    st.code(email_draft(pr), language=None, wrap_lines=True)
    with st.expander("Structured request (JSON)", icon=":material/data_object:"):
        st.json(pr.model_dump(mode="json"), expanded=True)
    if st.button("Done", type="primary", key=f"dlg_done_{pr.request_id}"):
        st.session_state.pop(done_key, None)  # the draft stays in the sidebar count
        close_dialog()
        st.rerun()
