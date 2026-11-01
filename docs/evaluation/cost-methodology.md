# Cost comparison methodology: serverless versus always-on

This document defines **how** to compare the cost of running the pipeline on
OpenFaaS with scale-to-zero against an always-on deployment. It contains no
measured costs. Every number below is a parameter to be filled from a real
run (see "Inputs to measure").

## Question

For one admission cycle, which costs less while meeting the latency target
(p95 intake < 2 s, every document decided within an agreed time)?

- **A. Serverless:** functions scale out with the queue and back to zero
  after the deadline; stateful services (PostgreSQL, object storage, NATS,
  Ollama) are always on.
- **B. Always-on:** the same code as long-running services sized for the
  peak, running for the whole cycle.

## Model

Cost over a cycle of `T` hours, priced as node-hours on the chosen host:

```
cost = Σ_nodes (node_hours × price_per_node_hour) + storage + egress
```

For **A**, node-hours follow load:

```
node_hours_A = baseline_nodes × T + Σ_t max(0, nodes_needed(t) − baseline_nodes) × Δt
nodes_needed(t) = ceil( Σ_f replicas_f(t) × cpu_request_f / allocatable_cpu_per_node )
```

where `replicas_f(t)` comes from the gateway's `gateway_service_count` series
recorded during the k6 run, and `baseline_nodes` hosts the stateful services
and the OpenFaaS control plane.

For **B**, capacity is fixed at the peak:

```
node_hours_B = (baseline_nodes + peak_function_nodes) × T
```

Cluster autoscaling (adding and removing nodes) is required for A to save
money; on a fixed-size cluster A only frees capacity for other workloads,
and the comparison becomes one of **utilisation**, which should then be
reported instead of cost.

## Inputs to measure

| Input | Source |
| --- | --- |
| Arrival profile over a cycle | Historical upload counts per hour, or the k6 profile as a proxy |
| `replicas_f(t)` | Prometheus `gateway_service_count` during the k6 run |
| CPU and memory per replica | Function `requests` and observed usage (`container_cpu_usage_seconds_total`) |
| Documents per replica-second | k6 throughput ÷ replica-seconds per function |
| Cold-start penalty | `load-tests/cold_warm.py` p50/p95 |
| Node price | The provider's on-demand or reserved hourly rate |
| Ollama node | GPU or large-CPU node; always-on in both options |

## Procedure

1. Deploy (infra/README.md) with monitoring enabled.
2. Run `load-tests/deadline_night.js` with the cycle's arrival profile scaled
   down proportionally, and record Prometheus data for the run.
3. Export `gateway_service_count` and the function CPU usage at 15-second
   resolution, and compute `nodes_needed(t)`.
4. Scale the result to a full cycle by mapping the k6 timeline onto the
   historical hourly profile.
5. Compute `node_hours_A` and `node_hours_B`, apply the price, add identical
   storage and egress to both, and report both totals with the latency
   achieved by each.
6. Repeat with the cold-start penalty applied, to confirm A still meets the
   latency target at the queue's busiest moments.

## Expected shape (hypothesis, not a result)

Admission traffic is bursty: most uploads arrive in a few days before each
deadline. A pays mostly for the always-on baseline (stateful services and
Ollama) and for function nodes only during bursts. B pays for peak capacity
all cycle. The gap should therefore grow with the peak-to-average ratio of
the arrival profile. This is to be confirmed or refuted with measured data.

## Threats to validity

- The baseline (database, object storage, Ollama) may dominate both options,
  hiding the function savings; report it separately.
- OpenFaaS CE does not scale to zero (infra/README.md). Option A needs
  OpenFaaS Pro, or KEDA scaling on queue depth, and that licence or
  complexity cost belongs in the comparison.
- k6 traffic is synthetic; real uploads vary in size and quality, which
  changes OCR time per document.
