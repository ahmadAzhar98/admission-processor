# load-tests

Scripts that drive a **deployed** OpenFaaS gateway. None of them has been
run in this repository's environment (no gateway or k6 available); their
results in docs/evaluation.md are marked "to be measured".

| Script | Measures |
| --- | --- |
| `deadline_night.js` | k6 upload burst (2 → 80 uploads/s): latency, errors, scaling |
| `cold_warm.py` | Cold-start versus warm latency after scaling a function to zero |
| `prepare_payloads.py` | Picks synthetic images and writes the k6 payload index |

```bash
make synthetic APPLICATIONS=20
.venv/bin/python load-tests/prepare_payloads.py --count 200
k6 run -e GATEWAY=$OPENFAAS_URL -e KEY_UNI_A=... -e KEY_UNI_B=... -e KEY_UNI_C=... \
    --out json=results/k6.json load-tests/deadline_night.js
.venv/bin/python load-tests/cold_warm.py --function quality-check \
    --image synthetic/output/uni-a/app-00000/app-00000-00-cnic.png --api-key "$KEY_UNI_A"
```

Watch the Grafana "Admission pipeline" dashboard during the k6 run to see
replicas follow the arrival rate and the queue drain afterwards.
