import json
import logging

from google import genai

from pr_review.config import settings
from pr_review.review.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def call_gemini(user_prompt: str) -> dict:
    response = get_client().models.generate_content(
        model=settings.gemini_model,
        contents=[
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}]},
        ],
        config={
            "temperature": 0,
            "response_mime_type": "application/json",
        },
    )

    text = response.text or "{}"
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini response as JSON: %s", text[:500])
        result = {
            "score": 0,
            "summary": "Review failed: invalid AI response",
            "categories": {},
            "suggestions": [],
        }

    result.setdefault("score", 0)
    result.setdefault("summary", "")
    result.setdefault("categories", {})
    result.setdefault("suggestions", [])

    return result