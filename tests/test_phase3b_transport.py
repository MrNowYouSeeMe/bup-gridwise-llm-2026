
import json
from pathlib import Path

import httpx

import app.llm_interpreter as module


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "items": [
                                        {
                                            "note_index": 0,
                                            "applies": False,
                                            "directive_type": "no_op",
                                            "hours": [],
                                            "solar_quantity_mode": "none",
                                            "solar_quantity_value": 0,
                                            "reserve_quantity_mode": "none",
                                            "reserve_quantity_value": 0,
                                            "max_grid_kwh": 0,
                                            "explanation": "No schedule effect.",
                                        }
                                    ]
                                }
                            ),
                        }
                    ]
                }
            ]
        }


class FakeClient:
    def __init__(self):
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResponse()


def test_shared_transport_object_exists():
    assert isinstance(
        module._GRIDWISE_HTTP_CLIENT,
        httpx.Client,
    )


def test_call_model_uses_shared_transport(monkeypatch):
    fake = FakeClient()

    monkeypatch.setattr(
        module,
        "_GRIDWISE_HTTP_CLIENT",
        fake,
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "unit-test-key",
    )
    monkeypatch.setenv(
        "OPENAI_MODEL",
        "gpt-5.6-terra",
    )

    for index in range(2):
        result = module._call_model(
            scenario_id=f"transport-{index}",
            notes=["The cafeteria menu changes tomorrow."],
            battery_capacity_kwh=500,
            battery_minimum_energy_kwh=50,
            repair_feedback=None,
        )

        assert result["items"][0]["directive_type"] == "no_op"

    assert len(fake.calls) == 2


def test_semantic_lock_matches_runtime():
    lock_path = (
        Path(__file__).parent
        / "data"
        / "phase3b_semantic_lock.json"
    )

    lock = json.loads(
        lock_path.read_text(encoding="utf-8")
    )

    import hashlib

    prompt_hash = hashlib.sha256(
        module.SYSTEM_PROMPT.encode("utf-8")
    ).hexdigest()

    schema_hash = hashlib.sha256(
        json.dumps(
            module.MODEL_OUTPUT_SCHEMA,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert prompt_hash == lock["system_prompt_sha256"]
    assert schema_hash == lock["model_output_schema_sha256"]