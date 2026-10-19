"""Sidebar: session controls, scoring sliders and requester details."""

from __future__ import annotations

import streamlit as st

from procurement_agent.llm import model_id
from procurement_agent.ui import state
from procurement_agent.ui.state import OTHER_KEYS, REQUESTER_KEYS, WEIGHT_KEYS


def _save_config() -> None:
    config = state.current_config()
    try:
        config.save()
    except OSError as exc:
        st.session_state.sidebar_notice = ("error", f"Could not save config/scoring.json: {exc}")
        return
    st.session_state.file_config = config
    state.reset_sliders(config)  # show the normalized weights that were written
    st.session_state.sidebar_notice = ("success", "Saved to config/scoring.json")


def render_sidebar() -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown("### 🛒 Procurement Agent")
        st.caption(f"Claude on Amazon Bedrock · `{model_id()}`")

        # -- session ------------------------------------------------------------
        with st.container(border=True, key="session_panel"):
            st.markdown("**Session**")
            turns, drafts = len(ss.turns), len(ss.drafts)
            st.caption(f"{turns} search{'es' if turns != 1 else ''} · {drafts} draft request{'s' if drafts != 1 else ''}")
            st.button(
                "New chat", key="clear_chat", icon=":material/add_comment:",
                on_click=state.clear_chat, width="stretch",
            )

        # -- scoring --------------------------------------------------------------
        with st.container(border=True, key="scoring_panel"):
            st.markdown("**Scoring weights**")
            st.caption("Drag to change how offers are ranked. Results re-rank instantly.")
            labels = {"price": "Price", "delivery": "Delivery speed", "rating": "Rating"}
            for name, key in WEIGHT_KEYS.items():
                st.slider(labels[name], 0, 100, step=5, key=key, format="%d")

            config = state.current_config()
            share = " · ".join(f"{labels[n]} {config.weights[n]:.0%}" for n in WEIGHT_KEYS)
            if sum(ss[k] for k in WEIGHT_KEYS.values()) == 0:
                st.warning("All weights are zero, so they are treated as equal.", icon=":material/info:")
            st.caption(f"Effective mix: {share}")

            with st.expander("Filters and limits", icon=":material/tune:"):
                st.slider(
                    "Suspicious price threshold", 0.05, 0.90, step=0.05, key=OTHER_KEYS["suspicious_price_ratio"],
                    help="Drop offers priced below this share of the typical price for the search.",
                    format="%.2f",
                )
                st.slider(
                    "Score for a missing rating", 0.0, 1.0, step=0.05, key=OTHER_KEYS["missing_rating_score"],
                    help="Rating score given to offers without a rating (1.0 = a 5-star rating).",
                    format="%.2f",
                )
                st.slider(
                    "Supplier timeout (seconds)", 2.0, 20.0, step=1.0, key=OTHER_KEYS["supplier_timeout_seconds"],
                    help="Used for the next search; a slower supplier is reported as failed.",
                    format="%.0f",
                )

            cols = st.columns(2)
            cols[0].button(
                "Reset", key="reset_scoring", icon=":material/restart_alt:",
                on_click=state.reset_sliders, width="stretch",
                help="Back to the values in config/scoring.json",
            )
            cols[1].button(
                "Save", key="save_scoring", icon=":material/save:",
                on_click=_save_config, width="stretch",
                help="Write these values to config/scoring.json",
            )
            notice = ss.pop("sidebar_notice", None)
            if notice:
                getattr(st, notice[0])(notice[1])
            if ss.get("config_load_error"):
                st.error(f"config/scoring.json could not be read, using defaults: {ss.config_load_error}")

        # -- requester -------------------------------------------------------------
        with st.container(border=True, key="requester_panel"):
            st.markdown("**Requester**")
            st.caption("Used on purchase requests.")
            st.text_input("Name", key=REQUESTER_KEYS["name"], placeholder="Jane Doe")
            st.text_input("Department", key=REQUESTER_KEYS["department"], placeholder="Finance")
            st.text_input("Cost center", key=REQUESTER_KEYS["cost_center"], placeholder="CC-1040")
