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
    sev = str(sev).strip().lower()

    if sev in ("critical", "major", "crit", "p1", "sev1"):
        return "CRITICAL"
    if sev in ("warning", "warn", "medium", "high", "p2", "sev2"):
        return "MAJOR"
    # everything else becomes MINOR
    return "MINOR"


def normalize_severity(sev: str | None) -> str:
    if not sev:
        return "info"

    normalized = str(sev).strip().lower()

    if normalized in ("critical", "major", "crit", "p1", "sev1"):
        return "critical"
    if normalized in ("warning", "warn", "medium", "p2", "sev2"):
        return "warning"
    if normalized in ("low", "info", "minor", "informational", "p3", "sev3"):
        return "info"
    if normalized == "high":
        return "other"
    return "other"

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

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/ready")
async def readiness():
    # If client exists and is not closed, we are ready.
    global client
    try:
        if client and not client.is_closed:
            return {"ready": True}
    except Exception:
        pass
    raise HTTPException(status_code=503, detail="Not ready")

@app.post("/alert")
async def receive_alert(request: Request):
    """
    Accept both Grafana's webhook wrapper payload and array-only payloads.
    Enrich the inner alerts with ITSM labels and return the same structure
    as received. Optionally forward to Alertmanager if ALERTMANAGER_URL is set.
    """

    # 1) Read and log raw body for debugging
    raw_body = await request.body()
    print("\n================ RAW INCOMING ALERT ================")
    print(raw_body.decode())

    # 2) Parse JSON
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON received.")

    print("\n================ PARSED JSON =======================")
    print(json.dumps(payload, indent=2))

    # 3) Normalize: detect format (Grafana wrapper vs array-only)
    is_wrapper = isinstance(payload, dict) and "alerts" in payload and isinstance(payload["alerts"], list)
    if is_wrapper:
        alerts = payload["alerts"]  # Grafana format: { ..., "alerts": [ ... ] }
    elif isinstance(payload, list):
        alerts = payload            # Array-only format: [ ... ]
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported payload: must be an object with 'alerts' list (Grafana) or a top-level list of alert objects."
        )

    # 4) Enrich each alert
    enriched_alerts = []
    for alert in alerts:
        alert.setdefault("labels", {})
        alert.setdefault("annotations", {})
        labels = alert["labels"]
        source_severity = labels.get("severity")

        # --- Static labels
        labels["integration"] = "external"
        labels["itsm_enabled"] = "true"
        labels["itsm_environment"] = os.getenv("HOST_ENVIRONMENT", "development")  # or "production"
        labels["teams_enabled"] = "false"
        labels["namespace"] = os.getenv("ALERT_NAMESPACE", "monitoring")

        # Force severity to one of: critical, warning, info, other
        labels["severity"] = normalize_severity(labels.get("severity"))

        # --- Conditional labels when ITSM is enabled
        if labels["itsm_enabled"] == "true":
            labels["itsm_app_id"] = os.getenv("ITSM_APP_ID", "APPD-212426")
            labels["itsm_contract_id"] = os.getenv("ITSM_CONTRACT_ID", "10APP11846700")
            forced_event_id = os.getenv("ITSM_EVENT_ID")
            labels["itsm_event_id"] = forced_event_id if forced_event_id else generate_itsm_event_id()
            severity_for_itsm = source_severity if source_severity is not None else labels.get("severity", "info")
            labels["itsm_severity"] = compute_itsm_severity(severity_for_itsm)

        # --- Dynamic labels / metadata
        labels["cluster_name"] = os.getenv("CLUSTER_NAME", "unknown-cluster")
        labels["enriched_by"] = "fastapi-lifespan-proxy"
        alert["annotations"]["processed_at"] = "lifespan-proxy"

        enriched_alerts.append(alert)

    # 5) Rebuild the response in the SAME SHAPE as input
    if is_wrapper:
        enriched_body = dict(payload)  # preserve other top-level fields from Grafana
        enriched_body["alerts"] = enriched_alerts
    else:
        enriched_body = enriched_alerts

    print("\n================ ENRICHED JSON =====================")
    print(json.dumps(enriched_body, indent=2))

    # 6) Optional: Forward to Alertmanager, preserving SHAPE for the caller,
    #    but converting to Alertmanager's expected array format for forwarding.
    alertmanager_url = os.getenv("ALERTMANAGER_URL")
    if alertmanager_url:
        # Build the Alertmanager v2 payload: MUST be a top-level list of alerts
        if is_wrapper:
            am_payload = enriched_alerts  # extract only the alerts list
        else:
            am_payload = enriched_body    # already a list of alerts

        try:
            resp = await client.post(
                alertmanager_url,  # e.g., http://alertmanager:9093/api/v2/alerts
                json=am_payload,
                headers={"Content-Type": "application/json"},
            )
            print(f"Forwarded to Alertmanager → HTTP {resp.status_code}")
            if resp.status_code >= 300:
                print(f"ERROR forwarding to Alertmanager: HTTP {resp.status_code}")
                try:
                    print("Response body:", resp.text)
                except Exception:
                    pass
            else:
                print(f"Forwarded to Alertmanager → HTTP {resp.status_code}")
        except Exception as e:
            print("ERROR sending to Alertmanager:", e)

    # 7) Return enriched payload (same shape as received)
    return enriched_body

# ---------------------------------------------------------
# Manual development runner
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    HOST_BIND = os.getenv("HOST_BIND", "0.0.0.0")
    uvicorn.run("src.main:app", host=HOST_BIND, port=8080, reload=True)
