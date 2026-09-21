import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github import Github
    from github import Repository as GHRepo

logger = logging.getLogger(__name__)


def get_repo(g: "Github", full_name: str) -> "GHRepo":
    return g.get_repo(full_name)


def get_pr_diff(repo: "GHRepo", pr_number: int) -> str:
    pr = repo.get_pull(pr_number)
    files = list(pr.get_files())
    parts: list[str] = []
    for f in files:
        patch = getattr(f, "patch", None)
        if patch:
            parts.append(f"--- {f.filename}\n{patch}")
    return "\n\n".join(parts)


def get_pr_info(repo: "GHRepo", pr_number: int) -> dict:
    pr = repo.get_pull(pr_number)
    return {
        "number": pr.number,
        "title": pr.title,
        "body": pr.body or "",
        "head_sha": pr.head.sha,
        "base_branch": pr.base.ref,
        "head_branch": pr.head.ref,
        "changed_files": pr.changed_files,
        "additions": pr.additions,
        "deletions": pr.deletions,
    }


def post_pr_comment(repo: "GHRepo", pr_number: int, body: str) -> None:
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)


def post_pr_review(repo: "GHRepo", pr_number: int, body: str, commit_sha: str) -> None:
    pr = repo.get_pull(pr_number)
    commits = list(pr.get_commits())
    last_commit = commits[-1] if commits else None
    if last_commit:
        pr.create_review(
            commit=last_commit,
            body=body,
            event="COMMENT",
        )
    else:
        pr.create_issue_comment(body)