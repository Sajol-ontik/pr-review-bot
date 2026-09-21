from github import Auth, Github, GithubIntegration

from pr_review.config import settings


def get_integration() -> GithubIntegration:
    auth = Auth.AppAuth(settings.github_app_id, settings.private_key)
    return GithubIntegration(auth=auth)


def get_github_for_installation(installation_id: int) -> Github:
    integration = get_integration()
    return integration.get_github_for_installation(installation_id)