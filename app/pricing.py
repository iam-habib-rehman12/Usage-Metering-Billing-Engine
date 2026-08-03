from dataclasses import dataclass

MICRODOLLARS_PER_DOLLAR = 1_000_000
UNITS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class Pricing:
    api_call_microdollars: int = 1_000
    input_per_million_microdollars: int = 1_250_000
    cached_input_per_million_microdollars: int = 125_000
    output_per_million_microdollars: int = 10_000_000


PRICING = Pricing()


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def token_cost_microdollars(
    *, input_tokens: int, cached_input_tokens: int,
    output_tokens: int, reasoning_tokens: int,
    pricing: Pricing = PRICING,
) -> int:
    values = (input_tokens, cached_input_tokens, output_tokens, reasoning_tokens)
    if any(value < 0 for value in values):
        raise ValueError("Token counts cannot be negative")
    if cached_input_tokens > input_tokens:
        raise ValueError("Cached input tokens cannot exceed input tokens")
    fresh_input = input_tokens - cached_input_tokens
    billed_output = output_tokens + reasoning_tokens
    numerator = (
        fresh_input * pricing.input_per_million_microdollars
        + cached_input_tokens * pricing.cached_input_per_million_microdollars
        + billed_output * pricing.output_per_million_microdollars
    )
    return _ceil_div(numerator, UNITS_PER_MILLION)


def api_call_cost_microdollars(quantity: int, pricing: Pricing = PRICING) -> int:
    if quantity < 0:
        raise ValueError("Quantity cannot be negative")
    return quantity * pricing.api_call_microdollars

