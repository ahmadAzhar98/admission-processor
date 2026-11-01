# infra

| Path | Purpose |
| --- | --- |
| `compose/` | Local development services (Docker Compose) |
| `k8s/` | Stateful dependencies for a k3s cluster (Kustomize) |
| `monitoring/` | Prometheus scrape config, alert rules, Grafana dashboard |

## Local development

```bash
make up                  # postgres+pgvector, seaweedfs, redis, nats
make up PROFILE=llm      # ... plus ollama
make migrate
make test-integration
make down
```

Pull models once: `docker compose -f infra/compose/docker-compose.yml exec
ollama ollama pull qwen2.5:7b-instruct` and `... ollama pull nomic-embed-text`.

## k3s + OpenFaaS

These steps were written for this project but **have not been run end to end
in its CI**; treat them as a checklist and adjust versions.

```bash
# 1. Cluster and OpenFaaS (Community Edition)
curl -sfL https://get.k3s.io | sh -
arkade install openfaas --load-balancer=false
kubectl rollout status -n openfaas deploy/gateway

# 2. Dependencies
kubectl apply -f infra/k8s/namespace.yaml
kubectl -n admission create secret generic postgres-credentials --from-literal=password="$PG_PASSWORD"
kubectl -n admission create secret generic seaweedfs-s3-config --from-file=s3.json=./s3.json
kubectl apply -k infra/k8s

# 3. Function secrets (values never committed)
faas-cli secret create database-url --from-literal "postgresql://admission:$PG_PASSWORD@postgres.admission:5432/admission"
faas-cli secret create s3-access-key --from-literal "$S3_ACCESS_KEY"
faas-cli secret create s3-secret-key --from-literal "$S3_SECRET_KEY"
for t in uni-a uni-b uni-c; do
  faas-cli secret create $t-api-key   --from-literal "$(python -c "from common.auth import hash_api_key as h; print(h('$KEY'))")"
  faas-cli secret create $t-staff-key --from-literal "..."   # same, with the staff key
done
faas-cli secret create platform-admin-key --from-literal "..."

# 4. Schema and functions
kubectl -n admission port-forward svc/postgres 5432 &  AP_DATABASE_URL=... make migrate
faas-cli template store pull python3-http
faas-cli up -f stack.yml
```

`stack.yml` copies `libs/` and `tenants/` into every build context (ADR 0004).

## faasd (single VM)

faasd runs the same functions without Kubernetes and suits a pilot on one
VM. Install faasd, add the services from `compose/docker-compose.yml` to
`/var/lib/faasd/docker-compose.yaml` (faasd starts them as containers), then
create the same secrets with `faas-cli secret create` and run
`faas-cli up -f stack.yml`. faasd has no autoscaling: each function runs one
replica, which is enough to evaluate behaviour but not deadline-night load.

## Autoscaling

Every function carries `com.openfaas.scale.min/max` labels, and the async
steps also carry `com.openfaas.scale.zero: "true"`. **Scale-to-zero and
label-driven autoscaling need OpenFaaS Pro** (or an equivalent such as KEDA
on the NATS queue); OpenFaaS CE honours `min`/`max` only through manual
scaling. The labels document the intended policy either way.
