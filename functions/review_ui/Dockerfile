# Staff review UI: Streamlit behind the OpenFaaS of-watchdog in HTTP mode.
FROM ghcr.io/openfaas/of-watchdog:0.12.5 AS watchdog

FROM python:3.11-slim
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN useradd --create-home app
WORKDIR /home/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Mirror the repository layout so `functions.review_ui.client` imports.
COPY --chown=app:app . ./functions/review_ui
RUN touch functions/__init__.py
USER app

ENV PYTHONPATH=/home/app/functions/review_ui/libs:/home/app \
    fprocess="streamlit run functions/review_ui/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true" \
    mode=http \
    upstream_url=http://127.0.0.1:8501
EXPOSE 8080
CMD ["fwatchdog"]
