import os
from contextlib import asynccontextmanager  # New import for lifespan

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Pydantic Response Model
# -----------------------------------------------------------------------------


class GistResponse(BaseModel):
    """Defines the structured output for a single Gist."""

    id: str = Field(..., description="The unique ID of the GitHub Gist.")
    description: str | None = Field(None, description="The description of the Gist.")
    html_url: str = Field(..., description="The direct URL to the Gist on github.com.")
    files: list[str] = Field(
        ..., description="A list of filenames contained in the Gist."
    )


# -----------------------------------------------------------------------------
# Lifespan Context Manager and Global Client
# -----------------------------------------------------------------------------

# Declare the client globally, but don't initialize it here.
client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initializes the httpx client on startup and closes it on shutdown.
    This replaces the deprecated @app.on_event.
    """
    global client

    # --- STARTUP
    # The GITHUB_TOKEN environment variable will be read here if available
    github_token = os.getenv("GITHUB_TOKEN")

    auth_headers = {"User-Agent": "FastAPIGistAPI/1.0"}
    if github_token:
        auth_headers["Authorization"] = f"token {github_token}"
        print("INFO: Authenticated GitHub requests enabled.")

    client = httpx.AsyncClient(
        base_url="https://api.github.com", headers=auth_headers, timeout=5.0
    )

    yield

    await client.aclose()


# -----------------------------------------------------------------------------
# FastAPI Application & Async HTTP Client Setup
# -----------------------------------------------------------------------------

# Pass the lifespan function to the FastAPI constructor
app = FastAPI(
    title="GitHub Gists Public API",
    version="1.0.0",
    lifespan=lifespan,  # <-- Attach LIFESPAN HERE
)

# NOTE: The deprecated @app.on_event("shutdown") function is now removed.

# -----------------------------------------------------------------------------
# API Route Definition: /<username>
# -----------------------------------------------------------------------------


@app.get(
    "/{username}", response_model=list[GistResponse], summary="List a User's Public Gists"
)
async def get_user_gists(username: str):
    """
    Fetches public Gists for a given GitHub user asynchronously.
    """
    try:
        # ASYNC request using httpx
        response = await client.get(f"/users/{username}/gists")

        # 1. HANDLE 404 EXPLICITLY HERE (This is the fix)
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"GitHub user '{username}' not found or has no public Gists.",
            )

        # 2. Raise for ALL OTHER ERRORS (4xx/5xx)
        response.raise_for_status()  # Raises an exception for 4xx/5xx status codes

        gists_data = response.json()

        gist_list = []
        for gist in gists_data:
            # Extract filenames from the nested 'files' dictionary
            filenames = list(gist.get("files", {}).keys())

            gist_info = {
                "id": gist.get("id"),
                "description": gist.get("description") or "No description provided",
                "html_url": gist.get("html_url"),
                "files": filenames,
            }
            # The Pydantic model validates and formats the output
            gist_list.append(GistResponse(**gist_info))

        return gist_list

    except httpx.HTTPStatusError as e:
        # This catches all 4xx/5xx errors raised by response.raise_for_status()
        # (excluding the 404 we already handled).
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Error fetching data from GitHub API.",
        ) from None
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Could not connect to the GitHub API service."
        ) from None


# -----------------------------------------------------------------------------
# Uvicorn Launcher (for direct development run)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    HOST_BIND = os.getenv("HOST_BIND", "127.0.0.1")
    # Runs the application on http://127.0.0.1:8080 as requested
    uvicorn.run("src.main:app", host=HOST_BIND, port=8080, reload=True)
