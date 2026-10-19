"""Smoke tests for the Streamlit app. Only the welcome page is loaded, so no Claude calls."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from procurement_agent.comparison import ScoringConfig
from procurement_agent.ui.chat import EXAMPLE_CATEGORIES, EXAMPLES

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_welcome_page_loads_with_sliders_from_config():
    at = AppTest.from_file(APP, default_timeout=15).run()
    assert not at.exception
    sliders = {s.key: s.value for s in at.slider}
    weights = ScoringConfig.load().weights
    for name in ("price", "delivery", "rating"):
        assert sliders[f"w_{name}"] == round(weights[name] * 100)
    keys = {b.key for b in at.button}
    assert {"clear_chat", "reset_scoring", "save_scoring", "example_0"} <= keys


def test_all_zero_weights_warn_and_reset_restores_them():
    at = AppTest.from_file(APP, default_timeout=15).run()
    for key in ("w_price", "w_delivery", "w_rating"):
        at.slider(key=key).set_value(0).run()
    assert any("treated as equal" in w.value for w in at.warning)
    at.button(key="reset_scoring").click().run()
    assert at.slider(key="w_price").value == round(ScoringConfig.load().weights["price"] * 100)


def example_labels(at):
    return {b.label.replace("\\$", "$") for b in at.button if b.key and b.key.startswith("example_")}


def test_each_example_category_shows_its_prompts():
    at = AppTest.from_file(APP, default_timeout=15).run()
    first, *others = EXAMPLE_CATEGORIES
    assert example_labels(at) == set(EXAMPLE_CATEGORIES[first][2])
    for name in others:
        at.button_group(key="example_category").set_value(name).run()
        assert not at.exception
        assert example_labels(at) == set(EXAMPLE_CATEGORIES[name][2])


def test_examples_include_the_prompt_injection_attempts():
    guardrails = EXAMPLE_CATEGORIES["Guardrails"][2]
    assert any("Amazon Bedrock credentials" in p for p in guardrails)
    assert any("master API key" in p for p in guardrails)
    assert len(EXAMPLES) == len(set(EXAMPLES))  # each prompt has one stable button key
