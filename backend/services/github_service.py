"""
GitHub Integration Service
Fetches real data via GitHub REST API using a Personal Access Token.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
WEEK_AGO   = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


class GitHubService:
    def __init__(self, token: Optional[str] = None):
        self._token = token

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_summary(self, token: str) -> dict:
        """7-day summary: PRs, issues, commits, CI status."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Who am I?
                me = (await client.get(f"{GITHUB_API}/user", headers=self._headers(token))).json()
                username = me.get("login", "")

                # Search PRs opened or updated in last 7 days
                pr_search = await client.get(
                    f"{GITHUB_API}/search/issues",
                    headers=self._headers(token),
                    params={
                        "q": f"is:pr author:{username} updated:>{WEEK_AGO}",
                        "per_page": 10, "sort": "updated",
                    },
                )
                prs = pr_search.json().get("items", [])

                # PRs assigned for review
                review_search = await client.get(
                    f"{GITHUB_API}/search/issues",
                    headers=self._headers(token),
                    params={
                        "q": f"is:pr review-requested:{username} is:open",
                        "per_page": 5,
                    },
                )
                review_prs = review_search.json().get("items", [])

                # Open issues assigned to me
                issue_search = await client.get(
                    f"{GITHUB_API}/search/issues",
                    headers=self._headers(token),
                    params={
                        "q": f"is:issue assignee:{username} is:open",
                        "per_page": 5,
                    },
                )
                issues = issue_search.json().get("items", [])

                # Repos with recent activity
                repos = (await client.get(
                    f"{GITHUB_API}/user/repos",
                    headers=self._headers(token),
                    params={"sort": "pushed", "per_page": 5, "type": "owner"},
                )).json()

            def _state_color(pr):
                if pr.get("draft"): return "draft"
                labels = [l["name"].lower() for l in pr.get("labels", [])]
                if any("block" in l for l in labels): return "blocked"
                if pr.get("state") == "closed": return "merged"
                return "open"

            return {
                "username":    username,
                "avatar_url":  me.get("avatar_url", ""),
                "pull_requests": [
                    {
                        "id":       pr["number"],
                        "title":    pr["title"],
                        "repo":     pr["repository_url"].split("/")[-1],
                        "url":      pr["html_url"],
                        "state":    _state_color(pr),
                        "updated":  pr["updated_at"][:10],
                        "comments": pr.get("comments", 0),
                    }
                    for pr in prs
                ],
                "reviews_requested": [
                    {
                        "id":    pr["number"],
                        "title": pr["title"],
                        "repo":  pr["repository_url"].split("/")[-1],
                        "url":   pr["html_url"],
                    }
                    for pr in review_prs
                ],
                "open_issues": [
                    {
                        "id":    i["number"],
                        "title": i["title"],
                        "repo":  i["repository_url"].split("/")[-1],
                        "url":   i["html_url"],
                        "labels": [l["name"] for l in i.get("labels", [])],
                    }
                    for i in issues
                ],
                "recent_repos": [
                    {
                        "name":        r.get("name", ""),
                        "full_name":   r.get("full_name", ""),
                        "url":         r.get("html_url", ""),
                        "pushed_at":   r.get("pushed_at", "")[:10] if r.get("pushed_at") else "",
                        "open_issues": r.get("open_issues_count", 0),
                    }
                    for r in (repos if isinstance(repos, list) else [])
                ],
            }
        except Exception as e:
            logger.error(f"GitHub API error: {e}")
            raise

    async def get_recent_activity(self):
        return {"pull_requests": [], "repositories": []}


def create_github_service():
    return GitHubService()
