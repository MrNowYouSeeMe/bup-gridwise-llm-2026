# 3-Minute Video Script

## 0:00–0:25 — Problem

“GridWise receives 24 hours of demand, solar and tariff data, battery limits, and one to three natural-language operator notes. The system must understand those notes, apply the resulting hard constraints, and return a valid minimum-cost 24-hour schedule.”

## 0:25–1:10 — Architecture

Show this flow:

```text
Request
→ schema validation
→ GPT-5.6 Terra structured interpretation
→ deterministic guardrails
→ SciPy/HiGHS LP optimizer
→ independent replay validator
→ exact JSON response
```

Say explicitly:

“The LLM never generates the schedule. It only converts natural language into one of the six allowed directive types. Deterministic code validates the note mapping, hours, factors, reserve values and grid caps before the optimizer sees them.”

## 1:10–1:50 — Correctness

Show one example such as an 80% solar reduction.

Explain:

“An 80% reduction means 20% usable solar remains. Whole-hour intervals are start-inclusive and end-exclusive. The optimizer minimizes grid cost while enforcing battery state transitions, capacity and rate limits, effective solar, directives and end-of-day battery neutrality.”

Then:

“After optimization, a separate replay validator independently recomputes the schedule. Invalid optimizer output is never returned as success.”

## 1:50–2:25 — Verification

Show terminal results:

- full offline regression
- all 10 official public optimizer cases
- live model-backed E2E tests
- latency result
- concurrent request test
- Docker `/health`

Mention English, Bangla, Banglish and mixed-language robustness as additional tests, while the official English contract remains primary.

## 2:25–3:00 — Run and submission

Show:

```powershell
.\RUN_LOCAL.ps1
.\TEST_PUBLIC_SAMPLES_OFFLINE.ps1
docker build -t gridwise-llm:local-final .
```

Then open:

```text
GET /health
POST /optimize-energy
```

Finish:

“The deployed endpoint and Docker fallback use the same tested pipeline. Secrets are supplied only through environment variables and are not committed or baked into the image.”