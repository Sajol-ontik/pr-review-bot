from pr_review.config import settings
from pr_review.review.scoring import format_review_body, is_pass


def test_is_pass_above_threshold():
    settings.pass_threshold = 70
    assert is_pass(80) is True
    assert is_pass(70) is True


def test_is_pass_below_threshold():
    settings.pass_threshold = 70
    assert is_pass(69) is False
    assert is_pass(0) is False


def test_format_review_body_pass():
    settings.pass_threshold = 70
    result = {
        "score": 85,
        "summary": "Good code",
        "categories": {
            "bugs": {"score": 22, "findings": ["Line 5: potential null deref"]},
            "security": {"score": 21, "findings": []},
        },
        "suggestions": ["Add tests"],
    }
    body = format_review_body(result, 42, 70)
    assert "PASS" in body
    assert "85/100" in body
    assert "potential null deref" in body
    assert "Add tests" in body


def test_format_review_body_fail():
    settings.pass_threshold = 70
    result = {
        "score": 40,
        "summary": "Needs work",
        "categories": {},
        "suggestions": [],
    }
    body = format_review_body(result, 42, 70)
    assert "FAIL" in body
    assert "40/100" in body