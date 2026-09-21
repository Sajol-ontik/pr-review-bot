import hashlib
import hmac

from pr_review.config import settings
from pr_review.github.webhooks import verify_webhook_signature


def test_verify_signature_correct():
    settings.github_webhook_secret = "my-secret"
    raw = b'{"hello":"world"}'
    expected = "sha256=" + hmac.new(b"my-secret", raw, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(raw, expected) is True


def test_verify_signature_wrong():
    settings.github_webhook_secret = "my-secret"
    raw = b'{"hello":"world"}'
    assert verify_webhook_signature(raw, "sha256=deadbeef") is False


def test_verify_signature_no_secret():
    settings.github_webhook_secret = ""
    raw = b"data"
    assert verify_webhook_signature(raw, "") is True