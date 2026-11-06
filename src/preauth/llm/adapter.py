from typing import Protocol

from preauth.api.schemas import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return one provider-neutral completion."""
