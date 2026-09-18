import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import APP_NAME, APP_VERSION
from app.logging_config import configure_logging
from app.schemas import ScenarioRequest
from app.validation import semantic_validation_errors

configure_logging()
logger = logging.getLogger("gridwise.api")
app = FastAPI(title=APP_NAME, version=APP_VERSION)


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    logger.info(
        "request_start request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "request_unhandled_exception request_id=%s method=%s path=%s elapsed_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_end request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    request_id = request_id_of(request)
    details = []

    for error in exc.errors():
        details.append(
            {
                "location": [str(part) for part in error.get("loc", [])],
                "message": error.get("msg", "invalid value"),
                "type": error.get("type", "validation_error"),
            }
        )

    logger.warning(
        "request_validation_failed request_id=%s details=%s",
        request_id,
        details,
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_request",
            "message": "Request validation failed.",
            "details": details,
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request_id_of(request)
    logger.exception("internal_error request_id=%s", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Unexpected internal error.",
            "request_id": request_id,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/optimize-energy")
async def optimize_energy(payload: ScenarioRequest, request: Request):
    request_id = request_id_of(request)
    semantic_errors = semantic_validation_errors(payload)

    if semantic_errors:
        logger.warning(
            "semantic_validation_failed request_id=%s scenario_id=%s errors=%s",
            request_id,
            payload.scenario_id,
            semantic_errors,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "semantic_validation_error",
                "message": "The request structure is valid, but one or more values are invalid.",
                "details": semantic_errors,
                "request_id": request_id,
            },
        )

    payload.hours.sort(key=lambda item: item.hour)
    logger.info(
        "phase1_validation_passed request_id=%s scenario_id=%s notes=%s hours=%s",
        request_id,
        payload.scenario_id,
        len(payload.operator_notes),
        len(payload.hours),
    )

    # Intentional Phase-1 boundary. Phase 2 replaces this.
    return JSONResponse(
        status_code=500,
        content={
            "error": "pipeline_not_ready",
            "message": "Phase 1 validation passed. LLM interpretation is added in Phase 2.",
            "request_id": request_id,
        },
    )