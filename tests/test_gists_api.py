from collections.abc import Generator

import httpx  # Required for explicit Response object
import pytest
import respx
from starlette import status
from starlette.testclient import TestClient

# Import the application instance from the source module
from src.main import app


# --- Pytest Fixture ---
@pytest.fixture
def ac() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@respx.mock
def test_get_gists_success(ac: TestClient):
    """Tests successful retrieval and correct structure of public Gists."""
    test_user = "octocat"

    mock_gist_data = [
        {
            "id": "12345",
            "description": "A sample gist",
            "html_url": "https://gist.github.com/octocat/12345",
            "public": True,
            "files": {"README.md": {"size": 100}},
        },
        {
            "id": "67890",
            "description": None,
            "html_url": "https://gist.github.com/octocat/67890",
            "public": True,
            "files": {"app.py": {"size": 50}, "utils.js": {"size": 20}},
        },
    ]

    # FIX: Construct and pass httpx.Response via return_value
    github_route = respx.get(f"https://api.github.com/users/{test_user}/gists").mock(
        return_value=httpx.Response(status_code=status.HTTP_200_OK, json=mock_gist_data)
    )

    response = ac.get(f"/{test_user}")

    assert response.status_code == status.HTTP_200_OK
    assert github_route.called

    data = response.json()
    assert len(data) == 2

    # Assert correct data transformation
    assert data[1]["description"] == "No description provided"
    assert "app.py" in data[1]["files"]


@respx.mock
def test_get_gists_user_not_found(ac: TestClient):
    """Tests handling of a GitHub 404 response."""
    test_user = "nonexistentuserxyz123"

    # FIX: Construct and pass httpx.Response via return_value
    respx.get(f"https://api.github.com/users/{test_user}/gists").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_404_NOT_FOUND, json={"message": "Not Found"}
        )
    )

    response = ac.get(f"/{test_user}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert (
        data["detail"] == f"GitHub user '{test_user}' not found or has no public Gists."
    )


@respx.mock
def test_get_gists_github_server_error(ac: TestClient):
    """Tests handling of a GitHub 500 server error."""
    test_user = "testuser"

    # FIX: Construct and pass httpx.Response via return_value
    respx.get(f"https://api.github.com/users/{test_user}/gists").mock(
        return_value=httpx.Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    )

    response = ac.get(f"/{test_user}")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert data["detail"] == "Error fetching data from GitHub API."
