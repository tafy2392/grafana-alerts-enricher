import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
import json


import string
import secrets


def generate_itsm_event_id(length: int = 5) -> str:
    """Return a random uppercase alphabetic string of given length (default 5)."""
    alphabet = string.ascii_uppercase  # 'A'..'Z'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------
# Globals
# ---------------------------------------------------------

client: httpx.AsyncClient  # same structure as your original code

# ---------------------------------------------------------
# Lifespan: set up Async HTTP client (optional forwarding)
# ---------------------------------------------------------


def compute_itsm_severity(sev: str) -> str:
    sev = sev.lower()

    if sev == "critical":
        return "CRITICAL"
    if sev in ("major", "high"):
        return "MAJOR"
    # everything else becomes MINOR
    return "MINOR"

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
    Receives an alert (Grafana/Prometheus format), logs it, enriches it with
    required ITSM labels (static + conditional + dynamic), and returns the result.
    """

    # ---------------------------------------------------------
    # Read raw request body for debug logging
    # ---------------------------------------------------------
    raw_body = await request.body()
    print("\n================ RAW INCOMING ALERT ================")
    print(raw_body.decode())

    # ---------------------------------------------------------
    # Parse JSON body
    # ---------------------------------------------------------
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON received.")

    print("\n================ PARSED JSON =======================")
    print(json.dumps(payload, indent=2))

    # ---------------------------------------------------------
    # Enrich the alert payload
    # Grafana/Alertmanager sends a list[] of alerts
    # ---------------------------------------------------------
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=400,
            detail="Alert payload must be a JSON list of alert objects."
        )

    enriched_payload = []

    for alert in payload:
        # Ensure label & annotation sections exist
        alert.setdefault("labels", {})
        alert.setdefault("annotations", {})

        labels = alert["labels"]

        # ---------------------------------------------------------
        # STATIC LABELS (mandatory)
        # ---------------------------------------------------------
        labels["integration"] = "external"
        labels["itsm_enabled"] = "true"
        labels["itsm_environment"] = os.getenv("HOST_ENVIRONMENT", "development")  # or "production"
        labels["teams_enabled"] = "false"
        labels["namespace"] = "monitoring"

        # If missing, default to critical
        labels["severity"] = labels.get("severity", "info")

        # ---------------------------------------------------------
        # CONDITIONAL LABELS (required only when itsm_enabled=true)
        # ---------------------------------------------------------
        if labels["itsm_enabled"] == "true":
            labels["itsm_app_id"] = os.getenv("ITSM_APP_ID", "APPD-123456")
            labels["itsm_contract_id"] = os.getenv("ITSM_CONTRACT_ID", "10APP123456789")

            forced_event_id = os.getenv("ITSM_EVENT_ID")
            labels["itsm_event_id"] = forced_event_id if forced_event_id else generate_itsm_event_id()

            labels["itsm_severity"] = compute_itsm_severity(labels.get("severity", "info"))

        # ---------------------------------------------------------
        # DYNAMIC LABELS
        # ---------------------------------------------------------
        labels["cluster_name"] = os.getenv("CLUSTER_NAME", "unknown-cluster")

        # ---------------------------------------------------------
        # INTERNAL ENRICHMENT METADATA
        # ---------------------------------------------------------
        labels["enriched_by"] = "fastapi-lifespan-proxy"
        alert["annotations"]["processed_at"] = "lifespan-proxy"

        enriched_payload.append(alert)

    print("\n================ ENRICHED JSON =====================")
    print(json.dumps(enriched_payload, indent=2))

    # ---------------------------------------------------------
    # Optional: Forward to Alertmanager (if configured)
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
            print("ERROR sending to Alertmanager:", e)

    # ---------------------------------------------------------
    # Return enriched alert to caller
    # ---------------------------------------------------------
    return enriched_payload

# ---------------------------------------------------------
# Manual development runner
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    HOST_BIND = os.getenv("HOST_BIND", "0.0.0.0")
    uvicorn.run("src.main:app", host=HOST_BIND, port=8080, reload=True)
