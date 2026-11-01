# 0005. Run the review API and staff UI as OpenFaaS functions

- Status: accepted
- Date: 2026-11-01

## Context

Staff need an HTTP API over the review queue and a browser UI to correct
results. Both are long-lived web apps (FastAPI and Streamlit) rather than
request/response handlers, so they don't fit the `python3-http` template.
CLAUDE.md asks not to add top-level directories without agreement, and all
deployable units currently live under `functions/`.

## Decision

- Put the API in `functions/review_api` (FastAPI) and the UI in
  `functions/review_ui` (Streamlit), next to the pipeline functions.
- Build both with the OpenFaaS `dockerfile` language and run them behind
  `of-watchdog` in HTTP mode. OpenFaaS then routes, scales and monitors them
  like any other function, and they share the gateway's TLS and metrics.
- Keep the API on `min` scale 1 during admission season (staff expect an
  instant response); the UI may scale to zero outside office hours.
- Business logic sits in `review_api/service.py` and is unit-tested
  without a web server. The Streamlit app only talks to the API.

## Consequences

- One deployment mechanism for everything; no extra Kubernetes manifests.
- The `dockerfile` template means each image pins its own of-watchdog
  version, which must be bumped by hand.
- Streamlit's websocket sessions go through the gateway; sticky sessions are
  not guaranteed, so the UI keeps no server-side state beyond a page view.
