from pr_review.config import settings


def is_pass(score: int) -> bool:
    return score >= settings.pass_threshold


def format_review_body(review_result: dict, pr_number: int, threshold: int) -> str:
    score = review_result["score"]
    status = "✅ PASS" if is_pass(score) else "❌ FAIL"
    summary = review_result.get("summary", "No summary")
    categories = review_result.get("categories", {})
    suggestions = review_result.get("suggestions", [])

    lines = [
        f"## AI Code Review — {status}",
        "",
        f"**Score: {score}/100** (threshold: {threshold})",
        "",
        summary,
        "",
        "---",
        "",
    ]

    if categories:
        lines.append("### Category Breakdown")
        lines.append("")
        for cat_name, cat_data in categories.items():
            emoji_map = {
                "bugs": "🐛",
                "security": "🔒",
                "performance": "⚡",
                "maintainability": "🔧",
            }
            emoji = emoji_map.get(cat_name, "📌")
            cat_score = cat_data.get("score", 0) if isinstance(cat_data, dict) else 0
            lines.append(f"**{emoji} {cat_name.title()}** — {cat_score}/25")
            findings = cat_data.get("findings", []) if isinstance(cat_data, dict) else []
            for finding in findings:
                lines.append(f"- {finding}")
            lines.append("")

    if suggestions:
        lines.append("---")
        lines.append("")
        lines.append("### Suggestions")
        lines.append("")
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")

    lines.append("---")
    lines.append("*Powered by AI Code Review Bot*")

    return "\n".join(lines)