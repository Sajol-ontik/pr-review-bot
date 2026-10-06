import hashlib
import hmac
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from pr_review.config import settings
from pr_review.db.models import BranchConfig, Repository, Review
from pr_review.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"], redirect_slashes=False)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DbSession = Annotated[Session, Depends(get_db)]

SESSION_COOKIE = "pr_review_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7


def _session_secret() -> bytes:
    return settings.dashboard_password.encode()


def _session_token() -> str:
    expires = str(int(time.time()) + SESSION_MAX_AGE)
    signature = hmac.new(_session_secret(), expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _cookie_ok(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE, "")
    expires, _, signature = token.partition(".")
    if not expires or not signature:
        return False
    expected = hmac.new(_session_secret(), expires.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    try:
        return int(expires) > int(time.time())
    except ValueError:
        return False


def is_authenticated(request: Request) -> bool:
    # Only the sign-in cookie counts. A saved browser login header would
    # keep the dashboard open after Log out.
    return _cookie_ok(request)


def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error},
        status_code=status.HTTP_200_OK,
    )


def check_auth(request: Request):
    """Allow the page to render immediately.

    A 401 with WWW-Authenticate makes Chrome wait on its native login dialog
    before the dashboard can paint.
    """
    if is_authenticated(request):
        return None
    if request.method == "GET":
        return login_page(request)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


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


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username != settings.dashboard_username or password != settings.dashboard_password:
        return login_page(request, error="Invalid username or password")
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        _session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


@router.get("", response_class=HTMLResponse, name="dashboard")
@router.get("/", response_class=HTMLResponse, name="dashboard_slash", include_in_schema=False)
async def index(request: Request, db: DbSession):
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.is_enabled = not repo.is_enabled
    db.commit()
    ctx = _index_ctx(db)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.post("/repos/{repo_id}/delete")
async def delete_repo(request: Request, repo_id: int, db: DbSession):
    denied = check_auth(request)
    if denied is not None:
        return denied
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/repos/{repo_id}", response_class=HTMLResponse)
async def repo_detail(request: Request, repo_id: int, db: DbSession):
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
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
    denied = check_auth(request)
    if denied is not None:
        return denied
    branch = db.get(BranchConfig, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch config not found")
    branch.custom_instructions = custom_instructions
    db.commit()
    return RedirectResponse(
        url=f"/dashboard/repos/{branch.repo_id}", status_code=status.HTTP_303_SEE_OTHER
    )