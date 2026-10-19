"""Procurement Agent: Streamlit app.

Run with:
    venv/bin/streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st  # noqa: E402

from procurement_agent.ui import state  # noqa: E402
from procurement_agent.ui.chat import USER_AVATAR, render_turn, render_welcome, run_turn  # noqa: E402
from procurement_agent.ui.sidebar import render_sidebar  # noqa: E402
from procurement_agent.ui.results import md, render_audit_log  # noqa: E402
from procurement_agent.ui.state import Turn  # noqa: E402
from procurement_agent.ui.styles import apply_styles  # noqa: E402

st.set_page_config(page_title="Procurement Agent", page_icon="🛒", layout="wide")


def main() -> None:
    state.init_state()
    apply_styles()
    render_sidebar()
    config = state.current_config()

    st.markdown(
        '<div class="pa-hero"><h1>Procurement Agent</h1>'
        "<p>Search trusted suppliers, compare offers and prepare a purchase request.</p></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.turns and not st.session_state.pending_prompt:
        render_welcome()

    for turn in st.session_state.turns:
        render_turn(turn, config)

    prompt = st.chat_input("Describe what you need, e.g. two 27-inch monitors under $450 each")
    prompt = prompt or st.session_state.pop("pending_prompt", None)
    if prompt and prompt.strip():
        turn = Turn(user_text=prompt.strip())
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(md(turn.user_text))
        run_turn(turn, config)
        st.session_state.turns.append(turn)
        st.rerun()

    # Only the latest search has a log; it starts fresh with every new search.
    if st.session_state.turns:
        render_audit_log(st.session_state.turns[-1].audit)


main()
