

def build_review_prompt(
    diff_text: str,
    pr_info: dict,
    branch_instructions: str = "",
) -> str:
    parts = [
        f"## Pull Request #{pr_info['number']}: {pr_info['title']}",
        f"Branch: {pr_info['head_branch']} → {pr_info['base_branch']}",
        "",
    ]

    if pr_info.get("body"):
        parts.append(f"### Description\n{pr_info['body']}\n")

    if branch_instructions:
        parts.append(f"### Branch-Specific Review Instructions\n{branch_instructions}\n")

    parts.extend([
        f"### Diff ({pr_info['changed_files']} files, "
        f"+{pr_info['additions']}/-{pr_info['deletions']})",
        f"```diff\n{diff_text}\n```",
    ])

    return "\n".join(parts)


SYSTEM_PROMPT = """\
You are an expert code reviewer. You analyze pull request diffs and provide a structured review.

You MUST respond with valid JSON matching this exact schema:
{
  "score": <int 0-100>,
  "summary": "<one paragraph overall assessment>",
  "categories": {
    "bugs": {"score": <int 0-25>, "findings": ["..."]},
    "security": {"score": <int 0-25>, "findings": ["..."]},
    "performance": {"score": <int 0-25>, "findings": ["..."]},
    "maintainability": {"score": <int 0-25>, "findings": ["..."]}
  },
  "suggestions": ["<actionable suggestion 1>", "<actionable suggestion 2>"]
}

Scoring guide:
- 0-29: Critical issues, do not merge
- 30-49: Significant problems, needs major revisions
- 50-69: Moderate issues, should be addressed before merge
- 70-89: Good quality with minor improvements possible
- 90-100: Excellent, ready to merge

Be constructive and specific. Reference file names and line numbers when possible.
"""