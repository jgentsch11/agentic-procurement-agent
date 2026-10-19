"""A small amount of CSS on top of the theme in .streamlit/config.toml.

Widgets with a `key` get a `st-key-<key>` class from Streamlit, which is what
these selectors target, so nothing depends on Streamlit's internal class names.
"""

import streamlit as st

CSS = """
<style>
/* Roomier main column */
.block-container { padding-top: 2.2rem; padding-bottom: 6rem; max-width: 1180px; }

/* Header */
.pa-hero h1 { font-size: 1.9rem; margin-bottom: 0.15rem; letter-spacing: -0.01em; }
.pa-hero p { color: #5B6475; margin-top: 0; }

/* Sidebar panels */
.st-key-session_panel, .st-key-scoring_panel, .st-key-requester_panel { background: #FFFFFF; }

/* Session buttons */
.st-key-clear_chat button { border-color: #C7D2FE; color: #4338CA; font-weight: 600; }
.st-key-clear_chat button:hover { background: #EEF2FF; border-color: #4F46E5; }
.st-key-save_scoring button { background: #4F46E5; color: #FFFFFF; border-color: #4F46E5; }
.st-key-save_scoring button:hover { background: #4338CA; color: #FFFFFF; }
.st-key-reset_scoring button:hover { border-color: #4F46E5; color: #4338CA; }

/* Welcome card and example prompts */
.st-key-welcome { background: linear-gradient(180deg, #FFFFFF 0%, #F5F6FF 100%); }
div[class*="st-key-example_"] button { justify-content: flex-start; text-align: left; height: 100%; }

/* Purchase panel under each result */
div[class*="st-key-buy_panel_"] { background: #FFFFFF; }

/* Chat bubbles: a little more air */
[data-testid="stChatMessage"] { padding: 0.9rem 1rem; }
</style>
"""


def apply_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
