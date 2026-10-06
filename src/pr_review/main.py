import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from pr_review.db.session import SessionLocal, get_db, init_db
from pr_review.github.webhooks import parse_github_webhook
from pr_review.review.orchestrator import handle_pr_event
from pr_review.web.dashboard import index as dashboard_index
from pr_review.web.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PR Review Bot", lifespan=lifespan, redirect_slashes=False)


@app.middleware("http")
async def do_not_cache_dashboard(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/dashboard"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


def run_review_in_background(payload: dict, delivery_id: str) -> None:
    """Process a pull_request webhook outside the request so GitHub gets an instant 200."""
    db = SessionLocal()
    try:
        from pr_review.db.models import ProcessedEvent

        existing = (
            db.query(ProcessedEvent)
            .filter(ProcessedEvent.delivery_id == delivery_id)
            .first()
        )
        if existing:
            return

        db.add(ProcessedEvent(delivery_id=delivery_id, event_type="pull_request"))
        db.commit()
        handle_pr_event(db, payload, delivery_id)
    except Exception:
        logger.exception("Webhook processing failed")
        db.rollback()
    finally:
        db.close()


@app.post("/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await parse_github_webhook(request)
    delivery_id = request.headers.get("x-github-delivery", "")
    event_type = request.headers.get("x-github-event", "unknown")

    if event_type == "pull_request":
        background_tasks.add_task(run_review_in_background, payload, delivery_id)

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request, db: Session = Depends(get_db)):
    # Serve the dashboard here. A redirect to /dashboard makes Chrome wait on the
    # basic-auth challenge and the page never finishes loading.
    return await dashboard_index(request, db)


app.include_router(dashboard_router)