import logging

from sqlalchemy.orm import Session

from pr_review.config import settings
from pr_review.db.models import BranchConfig, Repository, Review
from pr_review.github.auth import get_github_for_installation
from pr_review.github.client import get_pr_diff, get_pr_info, post_pr_review
from pr_review.review.gemini_client import call_gemini
from pr_review.review.prompts import build_review_prompt
from pr_review.review.scoring import format_review_body, is_pass

logger = logging.getLogger(__name__)


def get_branch_instructions(db: Session, repo_id: int, branch: str) -> str:
    config = (
        db.query(BranchConfig)
        .filter(
            BranchConfig.repo_id == repo_id,
            BranchConfig.branch == branch,
            BranchConfig.is_enabled,
        )
        .first()
    )
    return config.custom_instructions if config else ""


def handle_pr_event(db: Session, payload: dict, delivery_id: str) -> None:
    event_type = payload.get("action", "unknown")
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    full_name = repo_data.get("full_name", "")
    pr_number = pr_data.get("number", 0)
    head_sha = pr_data.get("head", {}).get("sha", "")
    base_branch = pr_data.get("base", {}).get("ref", "")
    installation_id = payload.get("installation", {}).get("id", 0)

    if not full_name or not pr_number:
        return

    repo_name = full_name.split("/")
    if len(repo_name) != 2:
        return
    owner, repo = repo_name

    db_repo = (
        db.query(Repository)
        .filter(Repository.owner == owner, Repository.repo == repo)
        .first()
    )

    if not db_repo:
        db_repo = Repository(
            owner=owner,
            repo=repo,
            installation_id=installation_id,
            is_enabled=True,
        )
        db.add(db_repo)
        db.flush()
    elif db_repo.installation_id != installation_id and installation_id:
        db_repo.installation_id = installation_id
        db.flush()

    if not db_repo.is_enabled:
        return

    if event_type in ("opened", "synchronize", "reopened"):
        review_existing = (
            db.query(Review)
            .filter(
                Review.repo_id == db_repo.id,
                Review.pr_number == pr_number,
                Review.commit_sha == head_sha,
            )
            .first()
        )
        if review_existing:
            return

        review = Review(
            repo_id=db_repo.id,
            pr_number=pr_number,
            commit_sha=head_sha,
            status="pending",
        )
        db.add(review)
        db.flush()
        try:
            _perform_review(db, db_repo, review, base_branch)
        except Exception as exc:
            logger.exception("Review failed for %s#%d", full_name, pr_number)
            review.status = "error"
            review.body = f"Review failed: {exc}"
            db.commit()


def _perform_review(db: Session, db_repo: Repository, review: Review, base_branch: str) -> None:
    g = get_github_for_installation(db_repo.installation_id)
    gh_repo = g.get_repo(f"{db_repo.owner}/{db_repo.repo}")

    pr_info = get_pr_info(gh_repo, review.pr_number)
    diff_text = get_pr_diff(gh_repo, review.pr_number)

    if len(diff_text) > settings.max_diff_chars:
        diff_text = diff_text[: settings.max_diff_chars] + "\n... (diff truncated)"

    branch_instructions = get_branch_instructions(db, db_repo.id, base_branch)
    user_prompt = build_review_prompt(diff_text, pr_info, branch_instructions)
    review_result = call_gemini(user_prompt)

    score = min(max(review_result.get("score", 0), 0), 100)
    body = format_review_body(review_result, review.pr_number, settings.pass_threshold)

    review.score = score
    review.status = "pass" if is_pass(score) else "fail"
    review.body = body
    db.commit()

    post_pr_review(gh_repo, review.pr_number, body, review.commit_sha)