from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from pr_review.config import settings
from pr_review.db.models import BranchConfig, Repository, Review
from pr_review.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DbSession = Annotated[Session, Depends(get_db)]


def check_auth(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    import base64

    decoded = base64.b64decode(auth[6:]).decode()
    username, _, password = decoded.partition(":")
    if username != settings.dashboard_username or password != settings.dashboard_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _index_ctx(db: Session) -> dict:
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    return {"repos": repos, "pass_threshold": settings.pass_threshold}


def _repo_ctx(db: Session, repo: Repository) -> dict:
    branches = (
        db.query(BranchConfig)
        .filter(BranchConfig.repo_id == repo.id)
        .order_by(BranchConfig.branch)
        .all()
    )
    reviews = (
        db.query(Review)
        .filter(Review.repo_id == repo.id)
        .order_by(Review.created_at.desc())
        .limit(20)
        .all()
    )
    return {"repo": repo, "branches": branches, "reviews": reviews}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: DbSession):
    check_auth(request)
    ctx = _index_ctx(db)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.post("/repos")
async def add_repo(
    request: Request,
    db: DbSession,
    owner: str = Form(...),
    repo: str = Form(...),
    installation_id: int = Form(...),
):
    check_auth(request)
    existing = (
        db.query(Repository)
        .filter(Repository.owner == owner, Repository.repo == repo)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Repository already exists")

    db_repo = Repository(owner=owner, repo=repo, installation_id=installation_id)
    db.add(db_repo)
    db.commit()

    ctx = _index_ctx(db)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.post("/repos/{repo_id}/toggle")
async def toggle_repo(request: Request, repo_id: int, db: DbSession):
    check_auth(request)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.is_enabled = not repo.is_enabled
    db.commit()
    ctx = _index_ctx(db)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.post("/repos/{repo_id}/delete")
async def delete_repo(request: Request, repo_id: int, db: DbSession):
    check_auth(request)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/repos/{repo_id}", response_class=HTMLResponse)
async def repo_detail(request: Request, repo_id: int, db: DbSession):
    check_auth(request)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    ctx = _repo_ctx(db, repo)
    return templates.TemplateResponse(request=request, name="repo_detail.html", context=ctx)


@router.post("/repos/{repo_id}/branches")
async def add_branch(
    request: Request,
    repo_id: int,
    db: DbSession,
    branch: str = Form(...),
    custom_instructions: str = Form(...),
):
    check_auth(request)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    existing = (
        db.query(BranchConfig)
        .filter(BranchConfig.repo_id == repo_id, BranchConfig.branch == branch)
        .first()
    )
    if existing:
        existing.custom_instructions = custom_instructions
    else:
        db.add(
            BranchConfig(
                repo_id=repo_id,
                branch=branch,
                custom_instructions=custom_instructions,
            )
        )
    db.commit()

    ctx = _repo_ctx(db, repo)
    return templates.TemplateResponse(request=request, name="repo_detail.html", context=ctx)


@router.post("/branches/{branch_id}/toggle")
async def toggle_branch(request: Request, branch_id: int, db: DbSession):
    check_auth(request)
    branch = db.get(BranchConfig, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch config not found")
    branch.is_enabled = not branch.is_enabled
    db.commit()
    return RedirectResponse(
        url=f"/dashboard/repos/{branch.repo_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/branches/{branch_id}/delete")
async def delete_branch(request: Request, branch_id: int, db: DbSession):
    check_auth(request)
    branch = db.get(BranchConfig, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch config not found")
    repo_id = branch.repo_id
    db.delete(branch)
    db.commit()
    return RedirectResponse(
        url=f"/dashboard/repos/{repo_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/branches/{branch_id}/update")
async def update_branch(
    request: Request,
    branch_id: int,
    db: DbSession,
    custom_instructions: str = Form(...),
):
    check_auth(request)
    branch = db.get(BranchConfig, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch config not found")
    branch.custom_instructions = custom_instructions
    db.commit()
    return RedirectResponse(
        url=f"/dashboard/repos/{branch.repo_id}", status_code=status.HTTP_303_SEE_OTHER
    )