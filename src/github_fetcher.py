"""GitHub Issue Fetcher for WordPress/Gutenberg repository."""

import requests
from typing import Optional


class GitHubFetcher:
    """Fetches open issues from GitHub repository."""

    BASE_URL = "https://api.github.com"
    DEFAULT_REPO = "WordPress/gutenberg"

    def __init__(self, token: str, repo: str = DEFAULT_REPO):
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def fetch_open_issues(
        self,
        per_page: int = 100,
        max_pages: Optional[int] = None,
        since: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch open issues (excluding PRs) from the repository.

        Args:
            per_page: Number of issues per page (max 100)
            max_pages: Maximum number of pages to fetch (None for all)
            since: Only fetch issues updated after this ISO 8601 timestamp

        Returns:
            List of issue dictionaries with relevant metadata
        """
        issues = []
        page = 1
        url = f"{self.BASE_URL}/repos/{self.repo}/issues"

        while True:
            params = {
                "state": "open",
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }
            if since:
                params["since"] = since

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            page_issues = response.json()
            if not page_issues:
                break

            for issue in page_issues:
                if "pull_request" in issue:
                    continue

                issues.append(self._extract_issue_data(issue))

            page += 1
            if max_pages and page > max_pages:
                break

        return issues

    def fetch_single_issue(self, issue_number: int) -> dict:
        """Fetch a single issue by number."""
        url = f"{self.BASE_URL}/repos/{self.repo}/issues/{issue_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return self._extract_issue_data(response.json())

    def _extract_issue_data(self, issue: dict) -> dict:
        """Extract relevant metadata from a GitHub issue."""
        labels = [label["name"] for label in issue.get("labels", [])]

        body = issue.get("body") or ""
        if len(body) > 2000:
            body = body[:2000] + "... [truncated]"

        return {
            "issue_id": issue["number"],
            "title": issue["title"],
            "url": issue["html_url"],
            "labels": labels,
            "body": body,
            "updated_at": issue["updated_at"],
            "created_at": issue["created_at"],
            "assignee": issue["assignee"]["login"] if issue.get("assignee") else None,
            "comments_count": issue.get("comments", 0),
        }

    def check_for_linked_prs(self, issue_number: int) -> bool:
        """Check if an issue has linked PRs via timeline events."""
        url = f"{self.BASE_URL}/repos/{self.repo}/issues/{issue_number}/timeline"
        headers = {**self.headers, "Accept": "application/vnd.github.mockingbird-preview+json"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            events = response.json()

            for event in events:
                if event.get("event") == "cross-referenced":
                    source = event.get("source", {}).get("issue", {})
                    if source.get("pull_request"):
                        return True
            return False
        except Exception:
            return False
