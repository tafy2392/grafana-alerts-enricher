import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
import json

# ---------------------------------------------------------
# Globals
# ---------------------------------------------------------

client: httpx.AsyncClient  # same structure as your original code

# ---------------------------------------------------------
# Lifespan: set up Async HTTP client (optional forwarding)
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initializes an httpx client on startup and closes it on shutdown.
    Matches your original design.
    """
    global client

    # Optional: use env var to configure Alertmanager forwarding
    alertmanager_url = os.getenv("ALERTMANAGER_URL")

    headers = {"User-Agent": "GrafanaAlertEnricher/1.0"}

    client = httpx.AsyncClient(
        timeout=5.0,
        headers=headers,
    )

    print("INFO: Alert Enrichment service started.")
    if alertmanager_url:
        print(f"INFO: Forwarding enabled → {alertmanager_url}")

    yield

    await client.aclose()
    print("INFO: HTTP client closed.")

# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title="Grafana Alert Enrichment Proxy",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------
# /alert endpoint: receives, logs, enriches alerts
# ---------------------------------------------------------

@app.post("/alert")
async def receive_alert(request: Request):
    """
    Receives Grafana or Prometheus-style alert JSON,
    logs it, enriches labels, and returns enriched JSON.
    """

    raw_body = await request.body()
    print("\n================ RAW INCOMING ALERT ================")
    print(raw_body.decode())

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("\n================ PARSED ALERT JSON ================")
    print(json.dumps(payload, indent=2))

    # ---------------------------------------------------------
    # Enrichment: add labels & annotations
    # Grafana/Alertmanager format is usually a list of alerts
    # ---------------------------------------------------------

    if isinstance(payload, list):
        enriched_payload = []

        for alert in payload:
            alert.setdefault("labels", {})
            alert.setdefault("annotations", {})

            # Add enrichment labels
            alert["labels"]["enriched_by"] = "fastapi-lifespan-proxy"
            alert["labels"]["environment"] = os.getenv("ENV", "dev")

            # Add annotation
            alert["annotations"]["processed_at"] = "lifespan-proxy"

            enriched_payload.append(alert)

    else:
        # Handle non-standard formats gracefully
        enriched_payload = {
            "original": payload,
            "note": "Non-standard alert structure; wrapping output"
        }

    print("\n================ ENRICHED ALERT JSON ================")
    print(json.dumps(enriched_payload, indent=2))

    # ---------------------------------------------------------
    # Optional: Forward to Alertmanager (disabled by default)
    # ---------------------------------------------------------

    alertmanager_url = os.getenv("ALERTMANAGER_URL")

    if alertmanager_url:
        try:
            resp = await client.post(
                alertmanager_url,
                json=enriched_payload,
                headers={"Content-Type": "application/json"},
            )
            print(f"Forwarded to Alertmanager → HTTP {resp.status_code}")
        except Exception as e:
            print("ERROR forwarding to Alertmanager:", e)

    return enriched_payload


# ---------------------------------------------------------
# Manual development runner
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    HOST_BIND = os.getenv("HOST_BIND", "127.0.0.1")
    uvicorn.run("src.main:app", host=HOST_BIND, port=8080, reload=True)
