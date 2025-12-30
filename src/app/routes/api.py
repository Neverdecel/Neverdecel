"""API routes for Ava chat and other endpoints."""

import hashlib
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ..ava.agent import AvaAgent
from ..ava.security import check_rate_limit

router = APIRouter()

# GitHub stats cache
_github_cache: dict = {}
_cache_ttl = 600  # 10 minutes


async def fetch_github_repo_data(repo: str) -> dict:
    """Fetch full repo data from GitHub with caching."""
    now = time.time()

    # Check cache
    if repo in _github_cache:
        cached_data, cached_time = _github_cache[repo]
        if now - cached_time < _cache_ttl:
            return cached_data

    # Fetch from GitHub API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{repo}",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                repo_data = {
                    "name": data.get("name", repo.split("/")[-1]),
                    "description": data.get("description") or "No description available",
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "language": data.get("language") or "Unknown",
                    "topics": data.get("topics", [])[:4],  # Limit to 4 topics
                    "url": data.get("html_url", f"https://github.com/{repo}"),
                }
                _github_cache[repo] = (repo_data, now)
                return repo_data
    except Exception:
        pass

    # Return cached data if available, else defaults
    if repo in _github_cache:
        return _github_cache[repo][0]
    return {
        "name": repo.split("/")[-1],
        "description": "No description available",
        "stars": 0,
        "forks": 0,
        "language": "Unknown",
        "topics": [],
        "url": f"https://github.com/{repo}",
    }

# Initialize Ava agent
ava = AvaAgent()


def _get_client_ip(request: Request) -> str:
    """Get client IP address, handling proxies."""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Take the first IP in the chain
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    # Hash the IP for privacy in logs
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


@router.post("/ava/chat", response_class=HTMLResponse)
async def chat_with_ava(request: Request, message: str = Form(...)):
    """
    Process a chat message with Ava.
    Returns HTML partial for HTMX to swap into the chat container.
    """
    templates = request.app.state.templates

    # Get client identifier for rate limiting
    client_id = _get_client_ip(request)

    # Check rate limit
    allowed, rate_error = check_rate_limit(client_id)
    if not allowed:
        return templates.TemplateResponse(
            request=request,
            name="components/message.html",
            context={
                "user_message": message,
                "ava_response": rate_error,
                "is_error": True,
            },
        )

    # Get response from Ava (now returns tuple)
    response, success = await ava.chat(message, session_id=client_id)

    # Render the message partial
    return templates.TemplateResponse(
        request=request,
        name="components/message.html",
        context={
            "user_message": message,
            "ava_response": response,
            "is_error": not success,
        },
    )


@router.get("/github/{owner}/{repo}/card", response_class=HTMLResponse)
async def get_repo_card(request: Request, owner: str, repo: str):
    """
    Get full GitHub repo card as HTML partial.
    Returns complete card HTML for HTMX to swap into the page.
    """
    templates = request.app.state.templates
    repo_data = await fetch_github_repo_data(f"{owner}/{repo}")

    return templates.TemplateResponse(
        request=request,
        name="components/repo_card.html",
        context={"repo": repo_data},
    )
