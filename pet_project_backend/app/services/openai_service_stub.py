import logging
from typing import Any, Dict


class OpenAIServiceStub:
    """Lightweight stub used in DOCS_MODE to avoid real OpenAI API initialization.

    Methods return deterministic placeholder payloads so that any incidental
    documentation-time invocation does not fail or trigger network calls.
    """

    def init_app(self, app):  # signature compatibility
        logging.info("OpenAIServiceStub: initialization skipped (DOCS_MODE)")

    def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
        return {
            "success": True,
            "stub": True,
            "image_url": "https://example.com/stub-cartoon.png",
            "image_description": "stub description (DOCS_MODE)",
            "final_prompt": "stub prompt",
            "revised_prompt": "stub prompt",
            "model_used": "stub"
        }

    def estimate_cost(self) -> Dict[str, Any]:
        return {
            "stub": True,
            "gpt4_vision_cost_usd": 0.0,
            "dalle3_cost_usd": 0.0,
            "total_cost_per_generation_usd": 0.0,
            "models": "stub",
            "note": "DOCS_MODE - cost unavailable"
        }

__all__ = ["OpenAIServiceStub"]
