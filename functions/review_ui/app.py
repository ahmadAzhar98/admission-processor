"""Streamlit staff UI for the review queue.

Run with ``streamlit run functions/review_ui/app.py``; the API location
comes from ``AP_REVIEW_API_URL``. The page keeps no server-side state
beyond the current session and makes every change through the API.
"""

import os

import streamlit as st
from common.errors import UpstreamServiceError

from functions.review_ui.client import ReviewClient, changed_fields

st.set_page_config(page_title="Admission review", layout="wide")
st.title("Admission document review")

with st.sidebar:
    api_url = st.text_input("API URL", os.environ.get("AP_REVIEW_API_URL", "http://127.0.0.1:8000"))
    tenant_id = st.text_input("Tenant ID", "uni-a")
    api_key = st.text_input("Staff key", type="password")
    reviewer = st.text_input("Your reviewer ID", "")

if not api_key or not reviewer:
    st.info("Enter the tenant, staff key and your reviewer ID to load the queue.")
    st.stop()

client = ReviewClient(api_url, tenant_id, api_key)
try:
    queue = client.queue()
except UpstreamServiceError as exc:
    st.error(str(exc))
    st.stop()

if not queue:
    st.success("The review queue is empty.")
    st.stop()

labels = {f"{q['document_type'] or 'unknown'} · {q['document_id']}": q for q in queue}
choice = st.selectbox(f"{len(queue)} documents waiting", list(labels))
document_id = labels[choice]["document_id"]
detail = client.detail(document_id)

left, right = st.columns(2)
with left:
    st.image(client.image(document_id), use_container_width=True)
with right:
    st.write("**Reasons:**", ", ".join(detail["item"]["reasons"]))
    for outcome in detail["validation"]:
        icon = "✅" if outcome["passed"] else "⚠️"
        st.write(f"{icon} `{outcome['rule_id']}` {outcome['message']}")
    st.subheader("Extracted fields")
    edited = {}
    for field in detail["fields"]:
        label = f"{field['name']} (confidence {field['confidence']:.2f}, {field['source']})"
        edited[field["name"]] = st.text_input(label, str(field["value"] or ""), key=field["name"])
    corrections = changed_fields(detail["fields"], edited)
    if corrections:
        st.caption(f"Corrections to save: {', '.join(sorted(corrections))}")
    approve, reject = st.columns(2)
    if approve.button("Approve", type="primary"):
        client.resolve(document_id, "approve", reviewer, corrections)
        st.rerun()
    if reject.button("Reject"):
        client.resolve(document_id, "reject", reviewer, corrections)
        st.rerun()
