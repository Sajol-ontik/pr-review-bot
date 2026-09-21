import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pr_review.db.session import SessionLocal, init_db
from pr_review.github.webhooks import parse_github_webhook
from pr_review.review.orchestrator import handle_pr_event
from pr_review.web.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "web" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PR Review Bot", lifespan=lifespan)


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


@app.get("/")
async def dashboard_index(request: Request):
    return RedirectResponse(url="/dashboard")


app.include_router(dashboard_router)