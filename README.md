# GridWise LLM — BUP CSE Fest 2026 Preliminary

A production-style submission for the **BUP CSE Fest 2026 Preliminary — GridWise LLM Smart Campus Energy Optimization Challenge**.

GridWise converts 1–3 natural-language operator notes into machine-checkable energy directives, validates the model output deterministically, solves a cost-minimizing 24-hour battery/solar/grid schedule with linear programming, independently replays the produced schedule, and returns the exact API response required by the challenge.

> **Submission status:** core implementation, accuracy regression, optimization, Docker fallback, fresh-clone reproducibility, external deployment, and external latency verification have all been completed. Repository/package visibility must follow the organizer's timing rules.

---

## Table of Contents

- [Submission Links](#submission-links)
- [What the System Does](#what-the-system-does)
- [Architecture](#architecture)
- [Why the Design Is Split Into LLM and Deterministic Layers](#why-the-design-is-split-into-llm-and-deterministic-layers)
- [Supported Directives](#supported-directives)
- [Directive Semantics](#directive-semantics)
- [Deterministic Guardrails](#deterministic-guardrails)
- [Optimization Model](#optimization-model)
- [Independent Replay Validation](#independent-replay-validation)
- [API Contract](#api-contract)
- [Quick Start — Windows PowerShell](#quick-start--windows-powershell)
- [Quick Start — Linux/macOS](#quick-start--linuxmacos)
- [Run and Test the API](#run-and-test-the-api)
- [Public Sample Validation](#public-sample-validation)
- [Final Verification Suite](#final-verification-suite)
- [Verified Test Results](#verified-test-results)
- [Docker Fallback](#docker-fallback)
- [Render Deployment](#render-deployment)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Logging and Error Handling](#logging-and-error-handling)
- [Security and Secret Handling](#security-and-secret-handling)
- [Known Limitations and Operational Notes](#known-limitations-and-operational-notes)
- [Dependencies and External Tools](#dependencies-and-external-tools)
- [Reproducibility Notes](#reproducibility-notes)
- [Repository / Submission Policy](#repository--submission-policy)

---

## Submission Links

### Public API

Base URL:

```text
https://bup-gridwise-llm-2026.onrender.com
```

Health endpoint:

```text
https://bup-gridwise-llm-2026.onrender.com/health
```

Expected response:

```json
{"status":"ok"}
```

Main optimization endpoint:

```text
POST https://bup-gridwise-llm-2026.onrender.com/optimize-energy
```

### Source Repository

```text
https://github.com/MrNowYouSeeMe/bup-gridwise-llm-2026
```

Repository visibility is managed according to the organizer rule: **private during the event, public after the submission deadline for evaluation**.

### Docker Fallback

Exact image tag:

```text
ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026:submission-c1713b7
```

Verified digest:

```text
sha256:11dbcbb5496c44ada0be9f4ee3cf4da5e37ed9f33bd31801b690e5e39545b179
```

The image was successfully published to GHCR and successfully pulled back during final verification.

### Relevant Repository Revisions

Runtime hardening baseline:

```text
c1713b7  perf: harden latency docker and reproducibility
```

Repository head after adding the GHCR publishing workflow:

```text
35c97be  ci: publish Docker fallback to GHCR
```

The second commit only adds the package-publishing workflow; it does not alter the runtime scheduling pipeline.

---

## What the System Does

For every valid scenario, the service:

1. validates the input request;
2. sends all 1–3 operator notes to the language-model interpretation layer in one call;
3. receives structured semantic interpretations;
4. treats that model output as untrusted;
5. applies deterministic schema and semantic guardrails;
6. converts valid interpretations into canonical GridWise directives;
7. applies those directives to the 24-hour optimization model;
8. solves for minimum grid electricity cost;
9. independently replays the candidate schedule;
10. recomputes summary metrics from the final plan;
11. returns the exact response structure required by the challenge.

High-level flow:

```text
Client JSON
    |
    v
FastAPI request validation
    |
    v
LLM operator-note interpretation
    |
    v
Deterministic normalization + guardrails
    |
    v
Canonical directives
    |
    v
24-hour LP optimizer (SciPy / HiGHS)
    |
    v
Independent replay validator
    |
    v
Recomputed totals + exact response JSON
```

The LLM **does not schedule battery/grid power**. It is used for the part where language understanding is required: converting natural-language operator notes into structured directives.

---

## Architecture

### 1. API and request validation

FastAPI receives the request and validates:

- `scenario_id`;
- `operator_notes`;
- exactly 24 hourly entries;
- hour identifiers;
- demand, solar, and tariff values;
- battery capacity, starting energy, reserve, and rate limits.

The request must contain **1–3 non-empty operator notes**.

The hourly input represents a complete day with unique hours `0..23`.

### 2. LLM semantic interpreter

All notes for one request are interpreted together.

The model is responsible only for semantic extraction:

- whether the note applies to the current 24-hour schedule;
- which supported directive it represents;
- affected whole hours;
- required numeric quantity and its semantic meaning.

The model used during the final verified runs was:

```text
gpt-5.6-terra
```

Provider/API path:

```text
OpenAI Responses API
```

The model identifier is configurable through `OPENAI_MODEL`.

### 3. Deterministic directive layer

The raw model result is not trusted.

`app/directives.py` validates and converts semantic model output into the exact canonical directive representation expected by the optimizer and API response.

This layer is responsible for:

- exact supported directive types;
- one interpretation per note;
- note-index mapping;
- `applies` semantics;
- hour normalization;
- numeric range validation;
- solar quantity conversion;
- reserve quantity conversion;
- final structured-adjustment shape.

### 4. LP optimizer

`app/optimizer.py` formulates the 24-hour scheduling problem as a linear program and solves it with SciPy's HiGHS-backed `linprog`.

The optimizer receives only already-validated canonical directives.

### 5. Independent replay

`app/replay.py` independently checks the generated plan rather than trusting the optimizer result.

It verifies:

- hourly energy balance;
- effective solar limits;
- battery transitions;
- capacity and reserve limits;
- charge/discharge limits;
- directive-specific restrictions;
- non-negative values;
- final battery neutrality;
- recomputed totals.

### 6. Pipeline orchestration

`app/pipeline.py` connects the interpreter, guardrails, optimizer, replay validator, and response construction.

`app/main.py` exposes the HTTP API and controlled error behavior.

---

## Why the Design Is Split Into LLM and Deterministic Layers

Natural-language interpretation and mathematical scheduling have different failure modes.

The design intentionally uses:

```text
LLM for language understanding
+
deterministic code for contracts and safety
+
LP solver for optimization
+
independent replay for verification
```

This prevents the model from directly inventing schedules, battery states, demand values, or unsupported constraints.

It also avoids hard-coded phrase matching as the sole interpreter. Equivalent paraphrases can be understood by the language model while deterministic code still controls what is allowed downstream.

---

## Supported Directives

The interpreter can resolve each note to exactly one of the following:

| Directive | Meaning |
|---|---|
| `solar_reduction` | Reduce usable solar during specified hours |
| `minimum_battery_reserve` | Raise the minimum battery energy during specified hours |
| `no_charge_window` | Battery charging is prohibited during specified hours |
| `no_discharge_window` | Battery discharging is prohibited during specified hours |
| `max_grid_window` | Grid import is capped during specified hours |
| `no_op` | The note does not affect the current 24-hour energy schedule |

For `no_op`:

```json
{
  "applies": false,
  "directive_type": "no_op",
  "structured_adjustment": null
}
```

For every non-`no_op` directive:

```text
applies = true
```

Exactly one `directive_interpretation` item is returned for each operator note, preserving `note_index` order.

---

## Directive Semantics

### Whole-hour time windows

The service follows the challenge convention:

```text
start-inclusive, end-exclusive
```

Examples:

```text
1 PM to 3 PM   -> [13, 14]
2 PM to 4 PM   -> [14, 15]
6 PM to 9 PM   -> [18, 19, 20]
13:00 to 15:00 -> [13, 14]
```

Hours in canonical directives are unique integers in `0..23` and are returned in ascending order.

### Solar semantics: "to" vs "by"

These meanings are intentionally kept distinct.

```text
"solar drops TO 20%"        -> usable fraction = 0.20
"solar reduced BY 20%"      -> usable fraction = 0.80
"80% reduction"             -> usable fraction = 0.20
"one-fifth of normal"       -> usable fraction = 0.20
"half remains"              -> usable fraction = 0.50
```

The LLM extracts the semantic quantity; deterministic code converts it to the official `factor` used by the optimizer.

### Battery reserve semantics

Examples:

```text
"keep at least 120 kWh"
-> absolute reserve = 120 kWh
```

```text
"keep at least 50% of capacity"
-> reserve fraction = 0.50
-> deterministic layer converts this to kWh using battery capacity
```

### Charge vs discharge

`no_charge_window` and `no_discharge_window` are different constraints and are never treated as synonyms.

### Grid cap

A `max_grid_window` note produces a non-negative hourly grid-import cap for the specified hours.

---

## Deterministic Guardrails

The model output is treated as **untrusted structured data** until validation succeeds.

The deterministic layer rejects unsafe or invalid semantic output such as:

- an unsupported directive type;
- missing note mappings;
- duplicate note mappings;
- incorrect note indexes;
- invalid `applies` semantics;
- hours outside `0..23`;
- invalid numeric quantities;
- solar factors outside `[0, 1]`;
- reserves below zero or above battery capacity;
- negative grid caps;
- malformed structured model output.

Safe normalization is limited to harmless canonicalization such as sorting and deduplicating valid hour values.

The system does **not** silently clamp semantically invalid values into validity.

There is no regex/keyword semantic fallback that replaces the required language-model interpretation path.

A limited structured repair attempt may be used when model output fails structural guardrails. If a valid safe interpretation cannot be obtained, the request fails in a controlled way rather than inventing constraints.

---

## Optimization Model

The objective is to minimize total grid electricity cost:

```text
minimize  sum(grid_kwh[h] * tariff_bdt_per_kwh[h])
          h=0..23
```

Subject to the challenge's energy and directive constraints.

### Energy balance

For every hour:

```text
grid
+ solar_used
+ battery_discharge
=
demand
+ battery_charge
```

### Solar

For every hour:

```text
0 <= solar_used <= effective_solar
```

Solar curtailment is allowed.

Grid export is not used.

### Battery state

Charging:

```text
E_after = E_before + battery_kwh
```

Discharging:

```text
E_after = E_before - battery_kwh
```

Idle:

```text
E_after = E_before
battery_kwh = 0
```

Battery state must remain within:

```text
active minimum reserve <= E <= capacity
```

Charge and discharge magnitudes must respect their hourly rate limits.

### End-of-day neutrality

The final battery state must equal the initial battery state:

```text
E_end = E_initial
```

### Directive application

Validated directives are incorporated before solving:

- `solar_reduction` changes effective solar;
- `minimum_battery_reserve` changes the active reserve floor;
- `no_charge_window` blocks charging;
- `no_discharge_window` blocks discharging;
- `max_grid_window` applies an hourly grid cap;
- `no_op` changes nothing.

---

## Independent Replay Validation

A solver success flag alone is not considered enough.

After optimization, the candidate plan is replayed independently hour by hour.

The replay layer verifies:

- exactly 24 plan rows;
- unique hours `0..23`;
- energy balance;
- solar usage vs effective available solar;
- battery action consistency;
- battery transition correctness;
- battery capacity and reserve limits;
- charge and discharge rate limits;
- directive compliance;
- non-negative required numeric fields;
- end-of-day battery neutrality;
- summary totals.

The API totals are recomputed from the final plan:

- `total_grid_kwh`;
- `total_cost_bdt`;
- `peak_grid_kwh`.

This makes the returned schedule independently auditable.

---

## API Contract

### `GET /health`

Readiness endpoint.

Request:

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### `POST /optimize-energy`

Accepts one complete 24-hour scenario.

Top-level request fields:

| Field | Requirement |
|---|---|
| `scenario_id` | String scenario identifier |
| `operator_notes` | Array of 1–3 non-empty natural-language strings |
| `hours` | Exactly 24 hourly records covering hours 0–23 |
| `battery` | Battery capacity/state/rate configuration |

Each hourly record contains:

```json
{
  "hour": 0,
  "demand_kwh": 180,
  "solar_kwh": 0,
  "tariff_bdt_per_kwh": 7
}
```

Battery object:

```json
{
  "capacity_kwh": 500,
  "initial_energy_kwh": 200,
  "minimum_energy_kwh": 50,
  "max_charge_kwh_per_hour": 100,
  "max_discharge_kwh_per_hour": 100
}
```

Required response top-level fields:

```text
scenario_id
directive_interpretation
hourly_plan
total_grid_kwh
total_cost_bdt
peak_grid_kwh
plan_summary
```

Each `directive_interpretation` entry contains:

```text
note_index
applies
directive_type
structured_adjustment
explanation
```

Each hourly plan row contains:

```text
hour
grid_kwh
solar_used_kwh
battery_action
battery_kwh
battery_energy_after_kwh
```

`battery_action` is one of:

```text
charge
discharge
idle
```

When the action is `idle`:

```text
battery_kwh = 0
```

---

## Quick Start — Windows PowerShell

The final submission was developed and verified on Windows with PowerShell.

Verified development Python:

```text
Python 3.14.2
```

### 1. Clone

```powershell
git clone https://github.com/MrNowYouSeeMe/bup-gridwise-llm-2026.git
cd bup-gridwise-llm-2026
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Set runtime configuration

Do not commit API keys.

For the current PowerShell session:

```powershell
$env:OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
$env:OPENAI_MODEL = "gpt-5.6-terra"
$env:GRIDWISE_LOG_LEVEL = "INFO"
$env:GRIDWISE_LOG_DIR = "logs"
```

### 5. Start locally

```powershell
.\RUN_LOCAL.ps1
```

Local URL:

```text
http://127.0.0.1:8000
```

Health:

```text
http://127.0.0.1:8000/health
```

---

## Quick Start — Linux/macOS

```bash
git clone https://github.com/MrNowYouSeeMe/bup-gridwise-llm-2026.git
cd bup-gridwise-llm-2026

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt

export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export OPENAI_MODEL="gpt-5.6-terra"
export GRIDWISE_LOG_LEVEL="INFO"
export GRIDWISE_LOG_DIR="logs"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Run and Test the API

### Health check — PowerShell

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health" `
    -Method Get
```

Expected:

```text
status
------
ok
```

### Health check — curl

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Executable optimization example — PowerShell

The following creates a complete 24-hour request without manually writing 24 rows.

```powershell
$hours = 0..23 | ForEach-Object {
    @{
        hour = $_
        demand_kwh = 100
        solar_kwh = 0
        tariff_bdt_per_kwh = 10
    }
}

$payload = @{
    scenario_id = "README-SMOKE-01"
    operator_notes = @(
        "The cafeteria menu changes tomorrow."
    )
    hours = $hours
    battery = @{
        capacity_kwh = 100
        initial_energy_kwh = 50
        minimum_energy_kwh = 50
        max_charge_kwh_per_hour = 0
        max_discharge_kwh_per_hour = 0
    }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/optimize-energy" `
    -Method Post `
    -ContentType "application/json" `
    -Body $payload
```

For this request, the note should be interpreted as `no_op`, and the returned object must contain the full 24-hour plan plus the required summary fields.

---

## Public Sample Validation

The repository contains the public sample test data used by the automated optimizer regression suite.

Run:

```powershell
.\TEST_PUBLIC_SAMPLES_OFFLINE.ps1
```

Final verified public optimizer check:

```text
20 passed
```

All 10 official public scenarios matched the expected optimal cost.

| Public Case | Verified Optimal Cost (BDT) |
|---|---:|
| SAMPLE-01 | 38365 |
| SAMPLE-02 | 42885 |
| SAMPLE-03 | 35480 |
| SAMPLE-04 | 40495 |
| SAMPLE-05 | 33950 |
| SAMPLE-06 | 34090 |
| SAMPLE-07 | 38550 |
| SAMPLE-08 | 37665 |
| SAMPLE-09 | 34873 |
| SAMPLE-10 | 41620 |

These checks validate optimizer quality independently of free-text response wording.

---

## Final Verification Suite

### Offline regression

```powershell
.\TEST_FINAL_OFFLINE.ps1
```

The offline suite intentionally disables real provider-backed tests so it can run deterministically and without API spend.

Final result:

```text
163 passed, 48 skipped
```

The 48 skipped tests are the live/provider-backed tests and are executed separately.

### Live semantic / full-pipeline accuracy

```powershell
.\TEST_FINAL_LIVE_ACCURACY.ps1
```

Requires a valid `OPENAI_API_KEY`.

Final full-pipeline regression:

```text
16/16 passed
```

This final gate included official public scenarios plus additional multilingual cases including Bangla, Banglish, and mixed-language notes.

### Full E2E latency

```powershell
.\TEST_FINAL_LATENCY.ps1
```

Final local verified result:

```text
count = 10
average = 2.924 s
p95 = 3.780 s
max = 4.004 s
```

All 10 public costs remained optimal during this performance run.

### Real concurrency

```powershell
.\TEST_FINAL_CONCURRENCY.ps1
```

Final verification:

```text
4/4 concurrent real E2E requests passed
wall time = 3.403 s
```

### External deployed endpoint

```powershell
.\FINAL_EXTERNAL_CHECK.ps1 `
    -BaseUrl "https://bup-gridwise-llm-2026.onrender.com"
```

Final externally measured result:

```text
/health: PASS
8 repeated optimize requests: PASS
external p95: 4.671 s
accuracy/latency gate: PASS
```

---

## Verified Test Results

Final verification completed on **2026-09-18**.

| Verification | Result |
|---|---|
| Offline regression | `163 passed` |
| Intentional offline skips | `48` live/provider-backed tests |
| Final real E2E accuracy | `16/16 passed` |
| Official public optimizer cases | `10/10 optimal` |
| Public optimizer assertions | `20 passed` |
| Real concurrent requests | `4/4 passed` |
| Local full-E2E p95 | `3.780 s` |
| External deployed p95 | `4.671 s` |
| Docker build | PASS |
| Docker `/health` | PASS |
| Docker real `/optimize-energy` | PASS |
| Docker image secret scan | PASS |
| Repository secret scan | PASS |
| Fresh-clone offline regression | PASS |
| Fresh-clone `/health` | PASS |
| GHCR publish | PASS |
| GHCR pull-back verification | PASS |

The challenge's full-score latency threshold is p95 `<= 5 s`; both the local full-E2E measurement and the final warm external measurement passed that gate.

---

## Docker Fallback

### Pull

```bash
docker pull ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026:submission-c1713b7
```

Verified digest:

```text
sha256:11dbcbb5496c44ada0be9f4ee3cf4da5e37ed9f33bd31801b690e5e39545b179
```

### Run — PowerShell

```powershell
docker run --rm `
    --name gridwise-llm `
    -p 8000:8000 `
    --env "OPENAI_API_KEY=$env:OPENAI_API_KEY" `
    --env "OPENAI_MODEL=gpt-5.6-terra" `
    --env "GRIDWISE_LOG_LEVEL=INFO" `
    ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026:submission-c1713b7
```

### Run — Bash

```bash
docker run --rm \
  --name gridwise-llm \
  -p 8000:8000 \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e OPENAI_MODEL="gpt-5.6-terra" \
  -e GRIDWISE_LOG_LEVEL="INFO" \
  ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026:submission-c1713b7
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

The image receives credentials only at runtime. No API key is baked into the image.

A local Docker helper is also included:

```powershell
.\RUN_DOCKER_LOCAL.ps1
```

---

## Render Deployment

The deployed service uses the repository `Dockerfile`.

Recommended/current settings:

```text
Service type: Web Service
Runtime / Language: Docker
Branch: main
Root directory: repository root
Dockerfile: ./Dockerfile
Health check path: /health
```

Required environment configuration:

```text
OPENAI_API_KEY=<runtime secret>
OPENAI_MODEL=gpt-5.6-terra
GRIDWISE_LOG_LEVEL=INFO
```

Do not commit `.env` or secret values.

Detailed handoff instructions are available in:

```text
DEPLOY_RENDER.md
```

Current deployed endpoint:

```text
https://bup-gridwise-llm-2026.onrender.com
```

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes for real LLM requests | Hosted model authentication |
| `OPENAI_MODEL` | Configurable | Model identifier; final verification used `gpt-5.6-terra` |
| `GRIDWISE_LOG_LEVEL` | Optional | Logging level; `INFO` used in final verification |
| `GRIDWISE_LOG_DIR` | Optional | Log directory; local default/workflow uses `logs` |

Example template:

```text
OPENAI_API_KEY=
OPENAI_MODEL=
GRIDWISE_LOG_LEVEL=INFO
GRIDWISE_LOG_DIR=logs
```

Never commit real values.

---

## Project Structure

```text
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── schemas.py
│   ├── validation.py
│   ├── directives.py
│   ├── llm_interpreter.py
│   ├── optimizer.py
│   ├── replay.py
│   └── pipeline.py
│
├── tests/
│   ├── data/
│   │   ├── public_sample_cases.json
│   │   └── phase3b_semantic_lock.json
│   ├── test_phase1.py
│   ├── test_phase2_guardrails.py
│   ├── test_phase2_interpreter_unit.py
│   ├── test_phase2_live_semantics.py
│   ├── test_phase3_api_offline.py
│   ├── test_phase3_live_e2e.py
│   ├── test_phase3_optimizer.py
│   ├── test_phase3_public_samples.py
│   ├── test_phase3_randomized.py
│   ├── test_phase3_replay_adversarial.py
│   └── test_phase3b_transport.py
│
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── pytest.ini
├── .env.example
├── RUN_LOCAL.ps1
├── RUN_DOCKER_LOCAL.ps1
├── TEST_PUBLIC_SAMPLES_OFFLINE.ps1
├── TEST_FINAL_OFFLINE.ps1
├── TEST_FINAL_LIVE_ACCURACY.ps1
├── TEST_FINAL_LATENCY.ps1
├── TEST_FINAL_CONCURRENCY.ps1
├── FINAL_EXTERNAL_CHECK.ps1
├── DEPLOY_RENDER.md
├── FINAL_SUBMISSION_CHECKLIST.md
└── VIDEO_SCRIPT.md
```

---

## Logging and Error Handling

The service uses structured application logs with request identifiers.

Typical request lifecycle events include:

```text
request_start
pipeline_start
llm_call
pipeline_complete
request_end
```

Logs are designed to provide operational traceability without exposing API keys.

Malformed or invalid requests are rejected with controlled client errors.

Model/provider or internal failures are handled in a controlled way and must not expose raw secrets or sensitive stack traces through the API response.

The implementation prioritizes:

```text
fail safely
rather than
invent a directive or schedule
```

---

## Security and Secret Handling

Security rules used by the submission:

- no API keys in Git;
- no `.env` with real credentials committed;
- no credentials baked into Docker images;
- no secret values included in API responses;
- no raw sensitive stack traces returned to clients;
- hosted-model credentials are supplied only through runtime environment variables;
- Docker image history was checked for secrets;
- repository secret checks passed during final hardening;
- operator notes are treated as untrusted input;
- model output is treated as untrusted structured data;
- note content cannot change the interpreter's role, schema, or allowed directive set.

The challenge uses synthetic input data only. The solution does not require live campus, billing, utility, or personal data.

---

## Known Limitations and Operational Notes

### Hosted-model dependency

Real semantic interpretation requires:

- a valid OpenAI API credential;
- network connectivity;
- sufficient provider quota;
- provider availability.

If the provider is unavailable or returns unusable structured output, the service fails safely rather than silently replacing the LLM with a keyword-based semantic interpreter.

### Supported directive scope

The service intentionally supports only the six directive types defined by the challenge.

It does not invent additional directive categories.

### 24-hour horizon

The API is designed specifically for the challenge's 24-hour schedule with hours `0..23`.

### Feasibility

The challenge states that organizer valid scenarios are feasible and do not contain mutually contradictory hard directives. The optimizer reports controlled failure behavior if it cannot produce a valid plan.

### Hosting cold starts

The final external p95 measurement of `4.671 s` was taken while the deployed service was available/warm.

A free hosting tier may cold-start after inactivity, so first-request latency after a long idle period can be higher than warm-state measurements.

### Floating-point tolerance

Scheduling and verification use floating-point arithmetic. Challenge comparisons are designed around the official numeric tolerance.

---

## Dependencies and External Tools

The project uses standard open-source/runtime components including:

- Python;
- FastAPI;
- Uvicorn;
- Pydantic;
- HTTPX;
- NumPy;
- SciPy;
- SciPy HiGHS / `linprog`;
- pytest;
- Docker;
- GitHub Actions / GHCR;
- OpenAI Responses API.

Exact Python dependency ranges are defined in:

```text
requirements.txt
```

The final Windows environment successfully installed and used:

```text
Python 3.14.2
NumPy 2.5.3
SciPy 1.18.1
```

No model training or fine-tuning is required at runtime.

---

## Reproducibility Notes

The final hardening workflow performed a clean fresh-clone check in a separate directory.

Verified from the clean copy:

```text
offline regression: PASS
/health startup check: PASS
```

This check was specifically used to detect undocumented local-machine assumptions.

Recommended reproducibility paths are:

### Source path

```text
clone
-> create venv
-> install requirements
-> set environment variables
-> start API
-> call /health
-> run a public-sample test
```

### Docker path

```text
docker pull exact-tag
-> supply OPENAI_API_KEY at runtime
-> docker run
-> call /health
-> call /optimize-energy
```

No judge-side source modification should be necessary.

---

## Repository / Submission Policy

The repository was created for this event solution and is managed according to the official event policy.

During the event:

```text
repository: private
```

After the official submission deadline, for evaluation:

```text
repository: public
```

The Docker package should likewise remain accessible to judges during the evaluation period.

Final submission artifacts include:

1. working public API endpoint;
2. source repository;
3. self-contained README/configuration documentation;
4. pullable Docker fallback image with exact tag/digest;
5. maximum 3-minute solution/architecture video.

---

## Final Submission Summary

```text
API:
https://bup-gridwise-llm-2026.onrender.com

Health:
https://bup-gridwise-llm-2026.onrender.com/health

Repository:
https://github.com/MrNowYouSeeMe/bup-gridwise-llm-2026

Docker:
ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026:submission-c1713b7

Docker digest:
sha256:11dbcbb5496c44ada0be9f4ee3cf4da5e37ed9f33bd31801b690e5e39545b179
```

The core submission path is:

```text
Natural-language notes
        |
        v
LLM semantic interpretation
        |
        v
Deterministic guardrails
        |
        v
Canonical constraints
        |
        v
Linear-programming optimizer
        |
        v
Independent replay validation
        |
        v
Exact GridWise response JSON
```
