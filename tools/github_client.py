# tools/github_client.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TypedDict

import httpx

from config import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {settings.github_pat}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class CommitInfo(TypedDict):
    """Represents a single GitHub commit within the investigation window."""
    sha: str
    short_sha: str
    message: str
    author: str
    committed_at: str
    changed_files: list[str]
    additions: int
    deletions: int
    risk_signals: list[str]


class GitHubClientError(Exception):
    """Raised when the GitHub API returns an unexpected error."""
    pass


class GitHubRateLimitError(GitHubClientError):
    """Raised when the GitHub API rate limit is exceeded."""
    pass


class GitHubNotFoundError(GitHubClientError):
    """Raised when the repository or resource is not found."""
    pass


def _extract_repo_path(github_repo_url: str) -> str:
    """Extract owner/repo path from a full GitHub URL.

    Args:
        github_repo_url: Full URL like https://github.com/org/repo

    Returns:
        Path string like 'org/repo'

    Raises:
        ValueError: If the URL is not a valid GitHub repository URL.
    """
    parts = github_repo_url.rstrip("/").split("github.com/")
    if len(parts) != 2 or not parts[1]:
        raise ValueError(f"Invalid GitHub URL: {github_repo_url}")
    return parts[1]


async def fetch_commits_in_window(
    github_repo_url: str,
    window_start: str,
    window_end: str,
) -> list[CommitInfo]:
    """Fetch all commits within the investigation window from GitHub.

    Args:
        github_repo_url: Full GitHub repository URL.
        window_start: ISO format string for window start.
        window_end: ISO format string for window end.

    Returns:
        List of CommitInfo dicts for commits within the window.

    Raises:
        GitHubNotFoundError: If the repository does not exist.
        GitHubRateLimitError: If the API rate limit is exceeded.
        GitHubClientError: For any other GitHub API error.
    """
    repo_path = _extract_repo_path(github_repo_url)
    url = f"{GITHUB_API_BASE}/repos/{repo_path}/commits"

    params = {
        "since": window_start,
        "until": window_end,
        "per_page": 50,
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        try:
            response = await _request_with_backoff(
                client=client,
                url=url,
                params=params,
            )

            commits_data = response.json()
            commits: list[CommitInfo] = []

            for commit in commits_data:
                sha = commit["sha"]
                short_sha = sha[:7]

                changed_files, additions, deletions = await _fetch_commit_files(
                    client, repo_path, sha
                )
                risk_signals = _detect_risk_signals(changed_files)

                commits.append(CommitInfo(
                    sha=sha,
                    short_sha=short_sha,
                    message=commit["commit"]["message"].split("\n")[0],
                    author=commit["commit"]["author"]["name"],
                    committed_at=commit["commit"]["author"]["date"],
                    changed_files=changed_files,
                    additions=additions,
                    deletions=deletions,
                    risk_signals=risk_signals,
                ))

            logger.info(
                f"Fetched {len(commits)} commits from {repo_path} "
                f"between {window_start} and {window_end}"
            )
            return commits

        except (GitHubNotFoundError, GitHubRateLimitError, GitHubClientError):
            raise
        except httpx.TimeoutException:
            raise GitHubClientError(
                f"GitHub API request timed out for {repo_path}"
            )


async def _fetch_commit_files(
    client: httpx.AsyncClient,
    repo_path: str,
    sha: str,
) -> tuple[list[str], int, int]:
    """Fetch the list of files changed in a specific commit.

    Args:
        client: An active httpx AsyncClient.
        repo_path: Repository path like 'org/repo'.
        sha: Full commit SHA.

    Returns:
        Tuple of (changed_file_paths, total_additions, total_deletions).
    """
    url = f"{GITHUB_API_BASE}/repos/{repo_path}/commits/{sha}"
    response = await client.get(url)

    if response.status_code != 200:
        logger.warning(f"Could not fetch files for commit {sha[:7]}")
        return [], 0, 0

    data = response.json()
    files = data.get("files", [])

    changed_files = [f["filename"] for f in files]
    additions = sum(f.get("additions", 0) for f in files)
    deletions = sum(f.get("deletions", 0) for f in files)

    return changed_files, additions, deletions


def _detect_risk_signals(changed_files: list[str]) -> list[str]:
    """Detect high-risk file changes that correlate with incidents.

    Args:
        changed_files: List of file paths changed in a commit.

    Returns:
        List of human-readable risk signal descriptions.
    """
    signals: list[str] = []

    for file_path in changed_files:
        file_lower = file_path.lower()

        for pattern in settings.high_risk_file_patterns:
            if pattern.lower() in file_lower:
                signals.append(f"High-risk file changed: {file_path}")
                break  # One signal per file is enough

    return signals


def calculate_time_to_first_error(
    committed_at: str,
    first_error_timestamp: str,
) -> int | None:
    """Calculate seconds between a deployment and the first error.

    Args:
        committed_at: ISO format commit timestamp from GitHub.
        first_error_timestamp: ISO format first error timestamp from logs.

    Returns:
        Seconds between deploy and first error, or None if unparseable.
    """
    try:
        deploy_time = datetime.fromisoformat(
            committed_at.replace("Z", "+00:00")
        )
        error_time = datetime.fromisoformat(
            first_error_timestamp.replace("Z", "+00:00")
        )

        if deploy_time.tzinfo is None:
            deploy_time = deploy_time.replace(tzinfo=timezone.utc)
        if error_time.tzinfo is None:
            error_time = error_time.replace(tzinfo=timezone.utc)

        delta = (error_time - deploy_time).total_seconds()
        return int(delta) if delta >= 0 else None

    except ValueError:
        logger.warning(
            f"Could not parse timestamps: "
            f"committed_at={committed_at}, "
            f"first_error={first_error_timestamp}"
        )
        return None
    
async def _request_with_backoff(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
    max_retries: int = 3,
) -> httpx.Response:
    """Make a GET request with exponential backoff on rate limit errors.

    Waits 2, 4, then 8 seconds between retries when GitHub returns 403.
    Raises GitHubRateLimitError if all retries are exhausted.

    Args:
        client: Active httpx AsyncClient with auth headers.
        url: Full GitHub API URL to request.
        params: Optional query parameters.
        max_retries: Maximum number of retry attempts.

    Returns:
        Successful httpx Response object.

    Raises:
        GitHubRateLimitError: If rate limit persists after all retries.
        GitHubNotFoundError: If the resource does not exist.
        GitHubClientError: For any other non-retryable error.
    """
    for attempt in range(max_retries):
        response = await client.get(url, params=params)

        if response.status_code == 200:
            return response

        if response.status_code == 404:
            raise GitHubNotFoundError(
                f"Resource not found: {url}"
            )

        if response.status_code == 403:
            # Check if it's a rate limit or a permission error
            response_data = response.json()
            is_rate_limit = (
                "rate limit" in response_data.get("message", "").lower()
                or response.headers.get("x-ratelimit-remaining") == "0"
            )

            if is_rate_limit and attempt < max_retries - 1:
                wait_seconds = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                logger.warning(
                    f"GitHub rate limit hit — waiting {wait_seconds}s "
                    f"before retry {attempt + 1} of {max_retries - 1}"
                )
                await asyncio.sleep(wait_seconds)
                continue

            raise GitHubRateLimitError(
                f"GitHub rate limit exceeded after {attempt + 1} attempts"
            )

        raise GitHubClientError(
            f"GitHub API error {response.status_code}: {response.text}"
        )

    raise GitHubRateLimitError(
        f"GitHub rate limit exceeded after {max_retries} attempts"
    )    