# 🐙 GitHub Gists Public API (FastAPI)

A high-performance, container-ready API built with **FastAPI** for
fetching **public GitHub Gists** . The
entire application runs from a compact, maintainable `main.py`, making
the project easy to understand and extend.

------------------------------------------------------------------------

## ✨ Features

-   ⚡ **FastAPI** -- automatic docs, high performance
-   🔧 **Single-file application logic** (`main.py`)
-   🧪 **Unit tests** powered by `pytest` + `respx`
-   🐳 **Docker & Docker Compose** ready

------------------------------------------------------------------------

## 🛡️ Code Quality and Type Safety

We use industry-leading tools, configured in `pyproject.toml`, to 
maintain high code quality:

* **Ruff** (Linter/Formatter): Used to enforce code style, 
automatically fix common errors, and prevent bugs. Ruff runs extremely fast 
and ensures code adheres to modern Python standards (PEP 8, Bugbear, etc.).
* **MyPy** (Static Type Checker): Used to check all Python code for type 
consistency. This ensures type errors are caught *before* the code runs, 
significantly reducing runtime exceptions and increasing code robustness.

-------------------------------------------------------------------------

## 🚀 Getting Started

### Prerequisites

Make sure you have:

-   **Python 3.11+**
-   **uv** (ultra-fast dependency installer)
-   **Docker** + **Docker Compose**

------------------------------------------------------------------------

## 1. Local Development Setup

This setup is ideal for coding and running tests.

### 1.1 Create Virtual Environment & Install Dependencies

``` bash
uv venv
source .venv/bin/activate
uv pip install -e .[test]
uv pip install --group dev
```

### 1.2 Run the API Server

``` bash
python -m src.main
```

Server will run at:

    http://127.0.0.1:8080

------------------------------------------------------------------------

## 🐳 2. Deployment with Docker

### 2.1 Docker Compose (Recommended)

Ensure `docker-compose.yaml` and `Dockerfile` are in your project root.

``` bash
docker compose up --build
```

API available at:

    http://localhost:8080

### 2.2 Plain Docker

Build the image:

``` bash
docker build -t fastapi-gists-api .
```

Run the container:

``` bash
docker run -d -p 8080:8080 -e GITHUB_TOKEN="${GITHUB_TOKEN}" -e HOST_BIND=0.0.0.0 --name gists-app fastapi-gists-api
```

With Github Token:

``` bash
 docker run -d  -p 8080:8080   -e GITHUB_TOKEN="${GITHUB_TOKEN}" -e HOST_BIND=0.0.0.0 --name gists-app fastapi-gists-api
```

------------------------------------------------------------------------

## 🧪 Running Tests

Run unit tests using **pytest**:

``` bash
source .venv/bin/activate
./.venv/bin/python -m pytest -v
```

------------------------------------------------------------------------

## 🔌 API Usage

### **GET /{username}** --- List Public Gists

Fetch public gists for any GitHub user.

  Parameter    Type    Required   Default   Description
  ------------ ------- ---------- --------- --------------------------
  `username`   path    Yes        N/A       GitHub username


### Example Request

    GET http://127.0.0.1:8080/octocat

### API Docs

Once the server is running: - Swagger UI →
**http://127.0.0.1:8080/docs** - Redoc → **http://127.0.0.1:8080/redoc**

------------------------------------------------------------------------

## 🔑 Environment Variables

  -----------------------------------------------------------------------
  Variable                       Description
  ------------------------------ ----------------------------------------
  `GITHUB_TOKEN`                 Optional: Increases GitHub rate limit to
                                 **5000 req/hr**

  -----------------------------------------------------------------------

If provided, the API uses token-authenticated GitHub requests.

------------------------------------------------------------------------

## 📂 Project Structure

    .
    ├── src/main.py
    ├── tests/
    ├── Dockerfile
    ├── docker-compose.yaml
    ├── pyproject.toml
    └── README.md

------------------------------------------------------------------------

## 🏁 Summary

This API provides a clean, modern, and scalable way to retrieve GitHub
Gists, with everything from local development to production-ready Docker
deployment covered.

Feel free to extend it with authentication, caching, or additional
GitHub endpoints! 🚀

## :warning: Please read these instructions carefully and entirely first
* Clone this repository to your local machine.
* Use your IDE of choice to complete the assignment.
* When you have completed the assignment, you need to  push your code to this repository and [mark the assignment as completed by clicking here](https://app.snapcode.review/submission_links/bfa0f030-ab56-480a-a169-4b5cef8d82d0).
* Once you mark it as completed, your access to this repository will be revoked. Please make sure that you have completed the assignment and pushed all code from your local machine to this repository before you click the link.