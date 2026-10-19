"""Smoke tests for the Streamlit app. Only the welcome page is loaded, so no Claude calls."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from procurement_agent.comparison import ScoringConfig

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_welcome_page_loads_with_sliders_from_config():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    sliders = {s.key: s.value for s in at.slider}
    weights = ScoringConfig.load().weights
    for name in ("price", "delivery", "rating"):
        assert sliders[f"w_{name}"] == round(weights[name] * 100)
    keys = {b.key for b in at.button}
    assert {"clear_chat", "reset_scoring", "save_scoring", "example_0"} <= keys


def test_all_zero_weights_warn_and_reset_restores_them():
    at = AppTest.from_file(APP).run()
    for key in ("w_price", "w_delivery", "w_rating"):
        at.slider(key=key).set_value(0).run()
    assert any("treated as equal" in w.value for w in at.warning)
    at.button(key="reset_scoring").click().run()
    assert at.slider(key="w_price").value == round(ScoringConfig.load().weights["price"] * 100)
