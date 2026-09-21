import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pr_review.config import settings
from pr_review.db.session import Base, engine

settings.github_webhook_secret = "test-secret"


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _sign(payload: dict) -> str:
    body = json.dumps(payload).encode()
    return "sha256=" + hmac.new(
        b"test-secret", body, hashlib.sha256
    ).hexdigest()


def _sign_body(body: bytes) -> str:
    return "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()


def test_health(client=None):
    from pr_review.main import app

    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "healthy"}


def test_webhook_valid_signature():
    from pr_review.main import app

    payload = {
        "action": "opened",
        "installation": {"id": 123},
        "repository": {"full_name": "acme/api-service"},
        "pull_request": {
            "number": 1,
            "title": "feat: add endpoint",
            "body": "Adds a new endpoint",
            "head": {"sha": "abc123", "ref": "feature-branch"},
            "base": {"ref": "main"},
        },
    }
    raw_body = json.dumps(payload).encode()
    with patch("pr_review.main.run_review_in_background"):
        with TestClient(app) as c:
            r = c.post(
                "/webhooks/github",
                content=raw_body,
                headers={
                    "X-Hub-Signature-256": _sign_body(raw_body),
                    "X-GitHub-Delivery": "evt-123",
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )
            assert r.status_code == 200


def test_webhook_invalid_signature():
    from pr_review.main import app

    payload = {"action": "opened"}
    with TestClient(app) as c:
        r = c.post(
            "/webhooks/github",
            json=payload,
            headers={
                "X-Hub-Signature-256": "sha256=wrong",
                "X-GitHub-Delivery": "evt-999",
            },
        )
        assert r.status_code == 401