// k6 load test: the last evening before an admission deadline.
//
// Uploads synthetic document images to the intake function at an arrival
// rate that ramps from a quiet baseline to a burst and back, the pattern
// that motivates serverless scaling. Run against a deployed gateway:
//
//   python load-tests/prepare_payloads.py --count 200
//   k6 run -e GATEWAY=http://127.0.0.1:8080 -e KEY_UNI_A=... -e KEY_UNI_B=... \
//          -e KEY_UNI_C=... load-tests/deadline_night.js
//
// SCENARIO=smoke runs a two-minute check instead of the full burst.
import http from "k6/http";
import { check } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Trend } from "k6/metrics";

const GATEWAY = __ENV.GATEWAY || "http://127.0.0.1:8080";
const KEYS = { "uni-a": __ENV.KEY_UNI_A, "uni-b": __ENV.KEY_UNI_B, "uni-c": __ENV.KEY_UNI_C };

const payloads = new SharedArray("payloads", () => JSON.parse(open("./payloads/index.json")));
const images = payloads.map((p) => open(p.path, "b"));

const duplicates = new Counter("duplicate_uploads");
const intakeLatency = new Trend("intake_latency", true);

const burst = {
  executor: "ramping-arrival-rate",
  startRate: 2,
  timeUnit: "1s",
  preAllocatedVUs: 50,
  maxVUs: 400,
  stages: [
    { target: 2, duration: "5m" },   // evening baseline
    { target: 40, duration: "10m" }, // portal reminder e-mails go out
    { target: 80, duration: "15m" }, // final hour before the deadline
    { target: 5, duration: "5m" },   // deadline passes
  ],
};

const smoke = { executor: "constant-arrival-rate", rate: 2, timeUnit: "1s", duration: "2m", preAllocatedVUs: 5 };

export const options = {
  scenarios: { uploads: __ENV.SCENARIO === "smoke" ? smoke : burst },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    intake_latency: ["p(95)<2000"],
  },
};

export default function () {
  const i = Math.floor(Math.random() * payloads.length);
  const doc = payloads[i];
  // A fresh application id per iteration models distinct applicants, so
  // uploads are not deduplicated; reusing ids would measure the cache.
  const applicationId = `${doc.application_id}-${__VU}-${__ITER}`;
  const response = http.post(`${GATEWAY}/function/intake`, images[i], {
    headers: {
      "Content-Type": "image/png",
      "X-Tenant-Id": doc.tenant_id,
      "X-Api-Key": KEYS[doc.tenant_id] || "",
      "X-Application-Id": applicationId,
      "X-Document-Type": doc.document_type,
    },
    tags: { tenant: doc.tenant_id },
  });
  intakeLatency.add(response.timings.duration);
  if (response.status === 200) duplicates.add(1);
  check(response, { "accepted (202/200)": (r) => r.status === 202 || r.status === 200 });
}
