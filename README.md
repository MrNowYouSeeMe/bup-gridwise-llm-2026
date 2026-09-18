# GridWise LLM — BUP CSE Fest 2026 Preliminary

GridWise is a 24-hour energy-scheduling API. It uses an LLM only to interpret 1–3 natural-language operator notes into a fixed directive schema, validates that structured interpretation deterministically, solves the energy schedule with linear programming, and independently replays the final plan before returning it.

## Architecture

```text
POST /optimize-energy
    |
    v
Pydantic request validation
    |
    v
OpenAI GPT-5.6 Terra
(one structured interpretation call for all notes)
    |
    v
Deterministic directive guardrails
    |
    v
SciPy / HiGHS linear-program optimizer
    |
    v
Independent replay validator
    |
    v
Exact response schema
```

The LLM never creates the hourly schedule. It only maps human notes to one of the six supported directive types:

- `solar_reduction`
- `minimum_battery_reserve`
- `no_charge_window`
- `no_discharge_window`
- `max_grid_window`
- `no_op`

The optimizer and replay validator are deterministic.

## Requirements

- Python 3.14 is the tested local version.
- OpenAI API access.
- Internet access for the hosted model.
- Docker is optional for local source execution but is the required fallback packaging path.

Main dependencies are FastAPI, Pydantic, HTTPX, SciPy/HiGHS, Uvicorn, and Pytest.

## Environment variables

Create a local `.env` file in the repository root:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-terra
GRIDWISE_LOG_LEVEL=INFO
GRIDWISE_LOG_DIR=logs
```

Never commit `.env` or API keys.

## Windows PowerShell quickstart

```powershell
cd E:\bup-gridwise-llm-2026
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\RUN_LOCAL.ps1
```

If `py.exe` is unavailable, create the virtual environment with the installed Python executable instead.

Service:

```text
http://127.0.0.1:8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

## API

### `GET /health`

Returns:

```json
{"status":"ok"}
```

### `POST /optimize-energy`

Request fields:

- `scenario_id`
- `operator_notes` — 1 to 3 non-empty strings
- `hours` — exactly 24 hour records covering 0 through 23
- `battery`

A successful response contains:

- `scenario_id`
- `directive_interpretation`
- `hourly_plan`
- `total_grid_kwh`
- `total_cost_bdt`
- `peak_grid_kwh`
- `plan_summary`

Every operator note maps to exactly one `directive_interpretation` entry in `note_index` order.

## Interpretation rules

Whole-hour windows are start-inclusive and end-exclusive. For example, 1 PM to 3 PM maps to `[13, 14]`.

For `solar_reduction`, `factor` is the usable fraction remaining. An 80% reduction therefore becomes `factor = 0.2`.

For `minimum_battery_reserve`, percentage-of-capacity wording is converted deterministically to kWh after the LLM identifies the semantic quantity.

`no_op` is the only directive with `applies=false` and `structured_adjustment=null`.

The service uses strict structured output plus deterministic validation. Unsupported or malformed model interpretations are not silently converted into invented constraints.

## Optimization

The schedule minimizes:

```text
sum(grid_kwh[h] * tariff_bdt_per_kwh[h]) for h = 0..23
```

while enforcing:

- hourly energy balance
- effective solar limits
- battery minimum/capacity bounds
- charge/discharge rate limits
- operator directives
- no grid export
- end-of-day battery neutrality

SciPy `linprog` with the HiGHS solver is used.

## Independent replay validation

The optimizer result is not trusted directly. A separate replay pass verifies:

- all 24 unique hours exist
- battery transitions are correct
- action/magnitude consistency
- battery bounds and rate limits
- directive application
- solar usage limits
- hourly energy balance
- final battery equals initial battery
- `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` are recalculated from the returned plan

An invalid optimized plan is never returned as a successful response.

## Testing

Full offline regression:

```powershell
.\TEST_PHASE3_OFFLINE.ps1
```

Official public optimizer pack:

```powershell
.\TEST_PUBLIC_SAMPLES_OFFLINE.ps1
```

Live full-pipeline LLM + optimizer + replay gate:

```powershell
.\TEST_PHASE3_LIVE_E2E.ps1
```

Final transport/reliability tests created by the final hardening phase:

```powershell
.\TEST_FINAL_OFFLINE.ps1
.\TEST_FINAL_LIVE_ACCURACY.ps1
.\TEST_FINAL_LATENCY.ps1
.\TEST_FINAL_CONCURRENCY.ps1
```

The repository includes the official 10-case public sample pack under `tests/data/public_sample_cases.json`. Tests compare interpretation/application and recalculated optimal cost; they do not require byte-for-byte equality with one reference hourly sequence.

## Docker fallback

Build:

```powershell
docker build -t gridwise-llm:local-final .
```

Run:

```powershell
docker run --rm `
  -p 8000:8000 `
  --env-file .env `
  -e PORT=8000 `
  gridwise-llm:local-final
```

Then verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The image binds Uvicorn to `0.0.0.0` and reads the port from `PORT`.

No secrets are copied into the image.

## Render handoff

Deployment itself is handled separately. Use the repository root as a Docker Web Service, set `/health` as the health-check path, and configure secrets in Render Environment rather than committing them.

Required environment variables:

```text
OPENAI_API_KEY
OPENAI_MODEL=gpt-5.6-terra
GRIDWISE_LOG_LEVEL=INFO
```

Do not manually set or hard-code the API key in Dockerfile, source code, README, or logs.

## Reliability and latency

The LLM semantic prompt, schema, model, reasoning effort, repair policy, and deterministic guardrails are accuracy-sensitive. Latency hardening is transport-only: the service reuses HTTP keep-alive connections rather than creating a new TCP/TLS client for every request.

A latency change is accepted only after the complete accuracy regression passes again.

Target:

- `/health` ready within 60 seconds
- valid `/optimize-energy` under 30 seconds
- p95 target `<= 5s`

## Error behavior

Malformed/structurally invalid requests receive controlled 4xx responses.

Semantic battery/request errors receive controlled validation responses.

Hosted-model/provider failure returns a controlled service error instead of a traceback or fabricated directive.

Optimizer infeasibility and internal replay failures are handled without leaking sensitive stack traces.

## Security

- `.env` is git-ignored.
- Secrets are never baked into Docker images.
- Raw API keys are not logged.
- Operator notes are treated as untrusted data.
- Model output is untrusted until deterministic guardrails pass.
- The repository contains only synthetic challenge data.

## Known limitations

- The service depends on OpenAI API availability, quota, credentials, and network latency.
- The challenge contract contains only the six published directive types.
- The implementation intentionally does not invent unpublished directives.
- The official challenge language is English; Bangla and Banglish are additionally tested for robustness but are not used to replace the official English path.
- Public sample schedules are references; equivalent optimal schedules may differ.

## Repository policy

Keep the repository private during the event. Follow the organizer rule for making it public after the submission deadline.

## Final artifacts

- Source repository
- public endpoint after deployment
- Docker fallback image
- self-contained README
- official public-sample test path
- final verification scripts
- maximum 3-minute solution video for tie-break readiness