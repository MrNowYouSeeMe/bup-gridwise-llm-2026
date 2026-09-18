# BUP GridWise LLM 2026

BUP CSE Fest 2026 preliminary solution.

## Architecture

Request -> API validation -> LLM interpretation -> deterministic guardrails -> LP optimizer -> replay validator -> JSON response

## Phase 1

Implemented: FastAPI foundation, exact `/health`, `/optimize-energy` request schema, structural validation, controlled errors, request IDs, logging, and automated tests.

LLM interpretation is intentionally added in Phase 2.

## Local commands

```powershell
cd E:\bup-gridwise-llm-2026
.\TEST_PHASE1.ps1
.\RUN_LOCAL.ps1
```

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Logs:

```powershell
.\SHOW_LOGS.ps1
```

Never commit `.env`, API keys, or tokens.