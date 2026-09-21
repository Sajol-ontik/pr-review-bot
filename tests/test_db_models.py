import pytest

from pr_review.db.models import BranchConfig, Repository, Review
from pr_review.db.session import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_repository_with_relations():
    db = SessionLocal()
    repo = Repository(owner="acme", repo="api", installation_id=42)
    db.add(repo)
    db.flush()

    db.add(BranchConfig(repo_id=repo.id, branch="main", custom_instructions="No secrets"))
    db.add(
        Review(
            repo_id=repo.id,
            pr_number=7,
            commit_sha="sha1",
            score=85,
            status="pass",
            body="# PASS",
        )
    )
    db.commit()

    fetched = db.query(Repository).first()
    assert fetched.owner == "acme"
    assert fetched.branch_configs[0].branch == "main"
    assert fetched.reviews[0].score == 85
    db.close()


def test_branch_config_unique():
    db = SessionLocal()
    repo = Repository(owner="acme", repo="api", installation_id=42)
    db.add(repo)
    db.flush()
    db.add(BranchConfig(repo_id=repo.id, branch="main"))
    db.commit()
    db.close()