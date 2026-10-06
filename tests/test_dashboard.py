from fastapi.testclient import TestClient

from pr_review.config import settings
from pr_review.db.session import Base, engine


def setup_module():
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)


def _login(client: TestClient) -> None:
    response = client.post(
        "/dashboard/login",
        data={
            "username": settings.dashboard_username,
            "password": settings.dashboard_password,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_dashboard_urls_render_without_redirect():
    from pr_review.main import app

    with TestClient(app) as client:
        _login(client)
        for path in ("/", "/dashboard", "/dashboard/"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 200, path
            assert "Add Repository" in response.text
            assert "no-store" in response.headers["cache-control"]


def test_dashboard_login_page_renders_immediately():
    from pr_review.main import app

    with TestClient(app) as client:
        for path in ("/", "/dashboard", "/dashboard/"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 200, path
            assert "www-authenticate" not in response.headers
            assert "Sign in" in response.text


def test_login_sets_session_cookie():
    from pr_review.main import app

    with TestClient(app) as client:
        response = client.post(
            "/dashboard/login",
            data={
                "username": settings.dashboard_username,
                "password": settings.dashboard_password,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
        assert "pr_review_session" in response.cookies

        page = client.get("/dashboard", follow_redirects=False)
        assert page.status_code == 200
        assert "Add Repository" in page.text
        assert "Log out" in page.text


def test_logout_clears_session():
    from pr_review.main import app

    with TestClient(app) as client:
        client.post(
            "/dashboard/login",
            data={
                "username": settings.dashboard_username,
                "password": settings.dashboard_password,
            },
            follow_redirects=False,
        )
        response = client.post("/dashboard/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert response.cookies.get("pr_review_session") in (None, "")

        page = client.get("/", follow_redirects=False)
        assert "Sign in" in page.text
        assert "Add Repository" not in page.text

        # A saved browser Authorization header must not reopen the dashboard.
        saved = client.get(
            "/dashboard",
            auth=(settings.dashboard_username, settings.dashboard_password),
            follow_redirects=False,
        )
        assert "Sign in" in saved.text
        assert "Add Repository" not in saved.text
