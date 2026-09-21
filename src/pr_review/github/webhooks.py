import hashlib
import hmac
import logging

from fastapi import HTTPException, Request

from pr_review.config import settings

logger = logging.getLogger(__name__)


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.github_webhook_secret:
        return True  # skip verification if no secret configured (dev mode)

    if not signature_header:
        return False

    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


async def parse_github_webhook(request: Request) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json

    payload = json.loads(raw_body)
    return payload