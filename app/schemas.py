from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GenerateRequest(BaseModel):
    usage_type: Literal["api_calls", "ai_tokens"]
    quantity: int = Field(default=1, ge=1)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_categories(self):
        if self.usage_type == "api_calls" and any(
            (self.input_tokens, self.cached_input_tokens,
             self.output_tokens, self.reasoning_tokens)
        ):
            raise ValueError("API-call events cannot include token categories")
        if self.usage_type == "ai_tokens":
            total = self.input_tokens + self.output_tokens + self.reasoning_tokens
            if total <= 0:
                raise ValueError("AI-token events require token counts")
            if self.cached_input_tokens > self.input_tokens:
                raise ValueError("Cached input cannot exceed input tokens")
            self.quantity = total
        return self


class CheckoutRequest(BaseModel):
    success_url: str | None = None
    cancel_url: str | None = None

