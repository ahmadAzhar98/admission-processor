# Review API: FastAPI behind the OpenFaaS of-watchdog in HTTP mode.
# faas-cli copies libs/ and tenants/ into this build context (stack.yml).
FROM ghcr.io/openfaas/of-watchdog:0.12.5 AS watchdog

FROM python:3.11-slim
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN useradd --create-home app
WORKDIR /home/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . ./function
USER app

ENV PYTHONPATH=/home/app/function/libs:/home/app \
    AP_TENANTS_DIR=/home/app/function/tenants \
    fprocess="uvicorn function.app:app --host 127.0.0.1 --port 8000" \
    mode=http \
    upstream_url=http://127.0.0.1:8000 \
    ready_path=/healthz
EXPOSE 8080
CMD ["fwatchdog"]
