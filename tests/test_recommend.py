"""Tests for the recommendation step. Claude is replaced by a fake client."""

import json
from types import SimpleNamespace

from procurement_agent.comparison import SearchRequest, compare
from procurement_agent.recommend import (
    RECOMMEND_PROMPT,
    RecommendationText,
    build_context,
    recommend,
    unverified_numbers,
)
from procurement_agent.suppliers import NorthStarSupplier, TechSourceSupplier


class FakeMessages:
    def __init__(self, text: RecommendationText):
        self.text = text
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.text, stop_reason="end_turn")


def fake_client(reasoning="Row 1 is the best fit.", caveats=()):
    return SimpleNamespace(messages=FakeMessages(RecommendationText(reasoning=reasoning, caveats=list(caveats))))


def monitor_result():
    request = SearchRequest(search_terms=["27 monitor"], quantity=2, max_unit_price=450, exclude=["arm", "mount"])
    return compare(request, suppliers=[NorthStarSupplier(), TechSourceSupplier()])


def test_top_and_runner_up_are_always_the_first_two_rows():
    result = monitor_result()
    rec = recommend(result, "two 27 inch monitors", client=fake_client())
    assert rec.top == result.groups[0]
    assert rec.runner_up == result.groups[1]


def test_claude_sees_only_the_top_rows_and_a_drop_summary():
    result = monitor_result()
    client = fake_client()
    recommend(result, "two 27 inch monitors", client=client)

    call = client.messages.calls[0]
    assert call["system"] == RECOMMEND_PROMPT
    assert call["output_format"] is RecommendationText
    sent = json.loads(call["messages"][0]["content"])
    assert len(sent["rows"]) == 5
    assert sent["rows_not_shown"] == len(result.groups) - 5
    assert sent["employee_request"] == "two 27 inch monitors"
    assert "Over budget" in sent["dropped_offers"]
    assert sum(sent["dropped_offers"].values()) == len(result.dropped)


def test_no_results_gives_no_rows():
    result = compare(SearchRequest(search_terms=["espresso machine"]), suppliers=[NorthStarSupplier()])
    rec = recommend(result, "an espresso machine", client=fake_client("Nothing matched.", ["Try a different item"]))
    assert rec.top is None and rec.runner_up is None
    assert rec.caveats == ["Try a different item"]


def test_numbers_from_the_data_pass():
    result = monitor_result()
    context = build_context(result, "x")
    best = result.groups[0].best
    second = result.groups[1].best
    unit = best.offer.price
    diff = abs(best.total_price - second.total_price)
    text = (
        f"It costs ${unit:,.2f} each, ${best.total_price:,.2f} total, ${round(unit)} rounded, "
        f"${diff:,.2f} more than the runner-up, arrives in {best.offer.delivery_estimate_days} days, "
        f"under the $450 budget."
    )
    assert unverified_numbers(text, context) == []


def test_invented_numbers_are_flagged():
    context = build_context(monitor_result(), "x")
    assert unverified_numbers("Only $1.23 and arrives in 99 days.", context) == ["$1.23", "99 days"]


def test_flagged_numbers_reach_the_recommendation():
    rec = recommend(monitor_result(), "x", client=fake_client("A bargain at $1.23.", ["Ships in 99 days"]))
    assert rec.unverified_numbers == ["$1.23", "99 days"]


def test_blank_caveats_are_dropped():
    rec = recommend(monitor_result(), "x", client=fake_client(caveats=["  ", "Low stock"]))
    assert rec.caveats == ["Low stock"]
