from pr_review.review.prompts import build_review_prompt


def test_build_review_prompt_contains_pr_info():
    pr_info = {
        "number": 5,
        "title": "Fix bug",
        "body": "Fixes the thing",
        "head_branch": "fix/thing",
        "base_branch": "main",
        "changed_files": 2,
        "additions": 10,
        "deletions": 2,
    }
    prompt = build_review_prompt("diff content", pr_info)
    assert "Fix bug" in prompt
    assert "fix/thing" in prompt
    assert "main" in prompt
    assert "diff content" in prompt
    assert "2 files" in prompt
    assert "+10/-2" in prompt


def test_build_review_prompt_includes_branch_instructions():
    pr_info = {
        "number": 5,
        "title": "Fix bug",
        "body": "",
        "head_branch": "fix",
        "base_branch": "main",
        "changed_files": 1,
        "additions": 1,
        "deletions": 0,
    }
    prompt = build_review_prompt("diff", pr_info, "No inline SQL")
    assert "No inline SQL" in prompt