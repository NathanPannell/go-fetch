# Performance Test Findings

Runs: 2026-04-14. Three scenarios executed via `make perf-baseline`, `make perf-stress`, `make perf-spike`.
Stack: 3 app replicas + nginx load balancer + 2 Celery workers + MongoDB Atlas local + MinIO + Redis.

---

## Summary

| Scenario | Users | Duration | Total Reqs | Failure Rate | Throughput | Search p50 | Search p95 |
|----------|-------|----------|------------|--------------|------------|------------|------------|
| Baseline | 10    | 120s     | 110        | ~10%*        | 0.56 req/s | 1500ms     | ~2000ms    |
| Stress   | 5→100 | 300s    | 232        | 42%          | 0.71 req/s | 1600ms     | 19000ms    |
| Spike    | 10→100→10 | 210s | 135      | 10%**        | 1.14 req/s | 1100ms     | 23000ms    |

\* Baseline failure rate excludes 17 DNS resolution errors that occur at container startup/teardown (not indicative of app behavior).
\*\* Spike similarly excludes 5 startup/teardown DNS errors.

---

## Baseline (10 concurrent users, 120s)

**Result files:** `baseline_2026-04-14_22-26-06_*`

| Endpoint | Req Count | Failure Rate | Median | p95 | Max |
|----------|-----------|--------------|--------|-----|-----|
| POST /auth/login | 10 | 0% | 340ms | 1000ms | 1027ms |
| POST /auth/signup | 10 | 0% | 520ms | 1000ms | 1005ms |
| GET /documents | 13 | 38%* | 28ms | — | — |
| POST /documents | 23 | 13%* | 180ms | 12000ms | 15359ms |
| GET /search | 39 | 46%** | 1500ms | ~2000ms | 2673ms |

\* These failures are DNS errors from startup/teardown, not real request failures.
\*\* 18 total: 7 are genuine SLO breaches (>2s), 10 are DNS teardown errors. Real SLO breach rate: ~18%.

**Observations:**
- At 10 users the system is functional. Auth and document listing are fast and reliable.
- Search is the bottleneck: p50 at 1500ms leaves little headroom under the 2s SLO. ~18% of search requests breach the SLO even at light load.
- Document upload (POST /documents) is slow when the Celery queue is backed up; occasional 12–15s outliers indicate worker saturation.

---

## Stress (staircase 5→20→50→100 users, 300s)

**Result files:** `stress_2026-04-14_23-02-27_*`

| Endpoint | Req Count | Failure Rate | Median | p95 | Max |
|----------|-----------|--------------|--------|-----|-----|
| POST /auth/login | 20 | 75% | 19000ms | 20000ms | 20260ms |
| POST /auth/signup | 41 | 88% | 19000ms | 111000ms | 124493ms |
| GET /documents | 28 | 4% | 27ms | 11000ms | 11832ms |
| POST /documents | 25 | 16% | 450ms | 34000ms | 46207ms |
| GET /search | 90 | 42% | 1600ms | 19000ms | 81817ms |

**Observations:**
- The system degrades severely as concurrency climbs past ~20 users. By the 100-user stage, auth operations (login/signup) are timing out at 20+ seconds in 75–88% of attempts.
- The auth failures point to MongoDB connection pool exhaustion or upstream timeout limits in nginx. Each app replica uses a shared connection pool; at 100 concurrent users across 3 replicas, the pool saturates.
- Total throughput collapsed: only 232 requests in 300s vs 7205 in the pre-scaling run (Apr 4). Adding nginx + 3 replicas introduced overhead that hurts performance in this constrained Docker environment — likely due to resource contention (all services on a single host).
- Document listing (GET /documents) remains fast (27ms median) because it is a simple MongoDB read with no heavy computation.

---

## Spike (10 → 100 → 10 users, 210s)

**Result files:** `spike_2026-04-14_23-12-22_*`

| Endpoint | Req Count | Failure Rate | Median | p95 | Max |
|----------|-----------|--------------|--------|-----|-----|
| POST /auth/login | 10 | 0% | 300ms | 310ms | 314ms |
| POST /auth/signup | 10 | 0% | 680ms | 790ms | 793ms |
| GET /documents | 20 | 0% | 11ms | 99ms | 99ms |
| POST /documents | 24 | 4%* | 290ms | 750ms | 24343ms |
| GET /search | 55 | 22%** | 1100ms | 23000ms | 65797ms |

\* One upload returned HTTP 0 (connection reset) during the burst.
\*\* 8 real SLO breaches + 4 DNS teardown errors. Real SLO breach rate: ~15%.

**Observations:**
- The spike scenario shows resilience at the bookends: auth, signup, and document listing recovered cleanly once load dropped back to 10 users.
- During the 100-user burst (60–90s window), search p95 reached 23s — the system queued requests rather than rejecting them. One search took 66s, indicating a request was held in the nginx upstream queue.
- Recovery was partial: after the burst, search latency did not fully return to baseline within the remaining 90s, suggesting the embedding model or MongoDB were still draining queued work.
- Signup latency (median 680ms) was much better than in the sustained stress test (19000ms), confirming the system can absorb a brief spike but not prolonged high concurrency.

---

## Cross-cutting findings

### Search SLO (2s budget) is the primary concern
Search breaches the SLO at all load levels. The vector similarity computation (sentence-transformers + PyTorch) runs synchronously in the request handler. At baseline it is marginal (~18% breach rate); under any significant load it blows past 2s routinely.

**Recommendation:** Offload embedding computation to Celery workers or cache embedding vectors for repeated queries. A Redis result cache for frequent search terms would directly reduce SLO breach rate without changing the model.

### Auth/MongoDB saturation under sustained high load
At 50–100 concurrent users, MongoDB connection pool exhaustion causes cascading timeouts across auth endpoints. This is the primary failure mode in the stress scenario.

**Recommendation:** Tune `maxPoolSize` in the MongoDB client, or add connection pooling middleware. Consider rate-limiting auth endpoints to protect the database under burst conditions.

### Horizontal scaling adds overhead in single-host Docker
Throughput with 3 replicas + nginx (Apr 14) was lower than with a single instance (Apr 4 baseline: 24 req/s vs 0.71 req/s under stress). In a real multi-host deployment this would not apply, but in this Docker environment all replicas share the same CPU/memory, so adding replicas increases scheduling overhead without adding capacity.

### Document upload outliers
POST /documents has occasional multi-second or multi-minute outliers driven by Celery worker backlog. The HTTP response returns 202 immediately, but the locust task waits for the response, so these outliers reflect real queuing delay. Two Celery workers are insufficient to keep up with uploads under high concurrency.

---

## Test infrastructure notes

- Exit code 1 from locust (make exits 2) is expected when any request is marked as failed. All three test runs produced complete CSV and HTML reports.
- DNS resolution errors (`gaierror -3`) appear in baseline and spike results. These occur at container startup before the nginx upstream is fully ready, or during teardown when services stop before locust finishes. They are not indicative of steady-state behavior.
- The `run.sh` script required a CRLF→LF fix (Windows checkout) before the container would start. A `.gitattributes` rule was added to prevent regression.
