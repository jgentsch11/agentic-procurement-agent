"""Tests for the request-understanding step. Claude is replaced by a fake client."""

from types import SimpleNamespace

import pytest

from procurement_agent.llm import (
    MAX_QUANTITY,
    UNDERSTAND_PROMPT,
    LLMError,
    RequestUnderstanding,
    understand_request,
)


def understanding(**kw) -> RequestUnderstanding:
    defaults = dict(
        is_product_request=True,
        summary="User wants a keyboard.",
        search_terms=["keyboard"],
        quantity=1,
        max_unit_price=None,
        must_have=[],
        exclude=[],
    )
    defaults.update(kw)
    return RequestUnderstanding(**defaults)


class FakeMessages:
    def __init__(self, parsed=None, stop_reason="end_turn", error=None):
        self.parsed, self.stop_reason, self.error = parsed, stop_reason, error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(parsed_output=self.parsed, stop_reason=self.stop_reason)


def fake_client(**kw):
    return SimpleNamespace(messages=FakeMessages(**kw))


# -- the Claude call --------------------------------------------------------------


def test_understand_request_sends_prompt_and_schema():
    client = fake_client(parsed=understanding())
    result = understand_request("I need an alphanumeric typing pad", client=client, model="m")

    assert result.search_terms == ["keyboard"]
    call = client.messages.calls[0]
    assert call["model"] == "m"
    assert call["system"] == UNDERSTAND_PROMPT
    assert call["output_format"] is RequestUnderstanding
    assert call["messages"] == [{"role": "user", "content": "I need an alphanumeric typing pad"}]


def test_empty_request_never_calls_claude():
    client = fake_client(parsed=understanding())
    with pytest.raises(ValueError):
        understand_request("   ", client=client)
    assert not client.messages.calls


def test_connection_failure_becomes_llm_error():
    with pytest.raises(LLMError, match="Could not reach Claude"):
        understand_request("monitor", client=fake_client(error=ConnectionError("no network")))


def test_refusal_becomes_llm_error():
    with pytest.raises(LLMError, match="declined"):
        understand_request("monitor", client=fake_client(parsed=None, stop_reason="refusal"))


def test_missing_parsed_output_becomes_llm_error():
    with pytest.raises(LLMError, match="no usable answer"):
        understand_request("monitor", client=fake_client(parsed=None, stop_reason="max_tokens"))


# -- hand-off to the comparison engine --------------------------------------------


def test_to_search_request_copies_fields():
    request = understanding(
        search_terms=["monitor", "27 inch monitor"],
        quantity=2,
        max_unit_price=450.0,
        must_have=["27"],
        exclude=["arm", "mount"],
    ).to_search_request()
    assert request.search_terms == ["monitor", "27 inch monitor"]
    assert request.quantity == 2
    assert request.max_unit_price == 450.0
    assert request.must_have == ["27"]
    assert request.exclude == ["arm", "mount"]


def test_to_search_request_rejects_non_product_requests():
    with pytest.raises(ValueError, match="weather"):
        understanding(
            is_product_request=False, summary="A question about the weather.", search_terms=[]
        ).to_search_request()


def test_to_search_request_rejects_empty_terms():
    with pytest.raises(ValueError):
        understanding(search_terms=["  ", ""]).to_search_request()


def test_to_search_request_clamps_bad_values():
    request = understanding(
        search_terms=["a", "b", "c", "d"], quantity=0, max_unit_price=-5, must_have=[" usb-c ", ""]
    ).to_search_request()
    assert request.search_terms == ["a", "b", "c"]
    assert request.quantity == 1
    assert request.max_unit_price is None
    assert request.must_have == ["usb-c"]

    assert understanding(quantity=10_000).to_search_request().quantity == MAX_QUANTITY
