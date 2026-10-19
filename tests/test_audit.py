"""Tests for the audit log: the log itself, the timings it relies on, and the panel in the app.

Claude is replaced by fakes and only the two local suppliers are searched, so nothing goes online.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from procurement_agent.audit import AuditLog
from procurement_agent.comparison import SearchRequest, search_all
from procurement_agent.llm import RequestUnderstanding, structured_call
from procurement_agent.recommend import Recommendation
from procurement_agent.suppliers import NorthStarSupplier, SupplierError, TechSourceSupplier

APP = str(Path(__file__).resolve().parents[1] / "app.py")


# -- the log ----------------------------------------------------------------------


def test_step_times_the_block_and_keeps_details():
    audit = AuditLog(request_text="a webcam")
    with audit.step("llm", "Understand the request (Claude)") as event:
        event.details.append("model: m")
    event = audit.events[0]
    assert event.status == "ok"
    assert event.duration_ms is not None
    assert event.details == ["model: m"]


def test_step_marks_errors_and_reraises():
    audit = AuditLog()
    with pytest.raises(RuntimeError):
        with audit.step("llm", "Write the recommendation (Claude)"):
            raise RuntimeError("throttled")
    event = audit.events[0]
    assert event.status == "error"
    assert event.details == ["error: throttled"]


def test_text_lists_every_step_and_a_summary():
    audit = AuditLog(request_text="two monitors")
    audit.add("request", "Request received")
    audit.add("llm", "Understand the request (Claude)", "model: m", duration_ms=1840)
    audit.add("supplier", "Search NorthStar", "offers found: 9", duration_ms=50)
    audit.add("supplier", "Search TechSource", "error: timed out", status="error", duration_ms=8000)
    text = audit.to_text()
    assert 'Request: "two monitors"' in text
    assert "LLM       Understand the request (Claude) · 1.84s · OK" in text
    assert "Search TechSource · 8.00s · ERROR" in text
    assert "offers found: 9" in text
    assert text.endswith("1 LLM call · 2 supplier searches")


# -- what the log is built from ---------------------------------------------------


class BrokenSupplier(NorthStarSupplier):
    name = "Broken Supplier"

    def search(self, query, *, limit=20):
        raise SupplierError(self.name, "HTTP 500")


def test_search_all_times_each_supplier():
    request = SearchRequest(search_terms=["monitor"])
    _, statuses = search_all(request, [NorthStarSupplier(), BrokenSupplier()])
    ok, broken = statuses
    assert ok.ok and ok.duration_ms is not None
    assert not broken.ok and broken.duration_ms is not None and "HTTP 500" in broken.error


def test_structured_call_reports_model_and_tokens():
    reply = SimpleNamespace(
        parsed_output=SimpleNamespace(), stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=612, output_tokens=148),
    )
    client = SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: reply))
    stats = {}
    structured_call("system", "content", RequestUnderstanding, client, "m", stats)
    assert stats == {"model": "m", "input_tokens": 612, "output_tokens": 148, "stop_reason": "end_turn"}


# -- the panel in the app ---------------------------------------------------------


def fake_understand(text, stats=None, **kw):
    stats.update(model="fake-model", input_tokens=600, output_tokens=150)
    if "weather" in text:
        return RequestUnderstanding(
            is_product_request=False, summary="A question about the weather.", search_terms=[],
            quantity=1, max_unit_price=None, must_have=[], exclude=[],
        )
    return RequestUnderstanding(
        is_product_request=True, summary="User wants a monitor.", search_terms=["monitor"],
        quantity=1, max_unit_price=None, must_have=[], exclude=[],
    )


def fake_recommend(result, user_request, stats=None, **kw):
    stats.update(model="fake-model", input_tokens=1900, output_tokens=230, rows_sent=3)
    return Recommendation(
        top=result.groups[0], runner_up=None,
        reasoning="SECRET-REASONING-TEXT", caveats=[], unverified_numbers=[],
    )


@pytest.fixture
def app(monkeypatch):
    from procurement_agent.ui import chat

    monkeypatch.setattr(chat, "understand_request", fake_understand)
    monkeypatch.setattr(chat, "recommend", fake_recommend)
    monkeypatch.setattr(chat, "default_suppliers", lambda: [NorthStarSupplier(), TechSourceSupplier()])
    monkeypatch.setattr("procurement_agent.ui.results.word_stream", lambda text, delay=0: iter([text]))
    return AppTest.from_file(APP, default_timeout=30).run()


def audit_panels(at):
    return [e for e in at.expander if e.label.startswith("Audit log")]


def test_no_audit_panel_before_the_first_search(app):
    assert not audit_panels(app)


def test_search_shows_one_collapsed_audit_panel(app):
    app.chat_input[0].set_value("a monitor").run()
    assert not app.exception
    [panel] = audit_panels(app)
    assert "2 LLM calls · 2 supplier searches" in panel.label
    [log] = [c.value for c in panel.code]
    for step in ("Request received", "Understand the request (Claude)", "Search NorthStar",
                 "Search TechSource", "Filter, score and group offers", "Write the recommendation (Claude)"):
        assert step in log
    assert "tokens: 600 in / 150 out" in log
    assert "SECRET-REASONING-TEXT" not in log  # Claude's text never goes in the log


def test_new_search_restarts_the_log(app):
    app.chat_input[0].set_value("a monitor").run()
    app.chat_input[0].set_value("what is the weather").run()
    [panel] = audit_panels(app)
    [log] = [c.value for c in panel.code]
    assert 'Request: "what is the weather"' in log
    assert "a monitor" not in log
    assert "Stopped: not a purchase request" in log
    assert "Search NorthStar" not in log


def test_purchase_draft_is_added_to_the_log(app):
    app.chat_input[0].set_value("a monitor").run()
    turn_id = next(b.key for b in app.button if b.key and b.key.startswith("purchase_")).split("_")[1]
    app.button(key=f"purchase_{turn_id}").click().run()
    app.checkbox(key=f"dlg_confirm_{turn_id}").check().run()
    app.button(key=f"dlg_create_{turn_id}").click().run()
    assert not app.exception
    [panel] = audit_panels(app)
    log = panel.code[0].value
    assert "Purchase request draft created" in log
    assert "nothing was ordered or sent" in log
