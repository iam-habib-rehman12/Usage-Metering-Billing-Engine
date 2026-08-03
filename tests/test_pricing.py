import pytest

from app.pricing import api_call_cost_microdollars, token_cost_microdollars


def test_api_call_cost_uses_integer_microdollars():
    assert api_call_cost_microdollars(25) == 25_000


def test_cached_input_is_priced_separately_and_cheaper():
    cost = token_cost_microdollars(
        input_tokens=1_000_000,
        cached_input_tokens=400_000,
        output_tokens=0,
        reasoning_tokens=0,
    )
    assert cost == 800_000


def test_reasoning_tokens_are_billed_as_output():
    cost = token_cost_microdollars(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=100_000,
        reasoning_tokens=50_000,
    )
    assert cost == 1_500_000


def test_cached_tokens_cannot_exceed_input():
    with pytest.raises(ValueError):
        token_cost_microdollars(
            input_tokens=10,
            cached_input_tokens=11,
            output_tokens=0,
            reasoning_tokens=0,
        )

