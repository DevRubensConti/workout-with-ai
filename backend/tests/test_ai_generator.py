import copy
import json
import math
import re
from collections import Counter
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from src.auth.models import User
from src.config import get_settings
from src.workouts.exercises.models import DisabledExercise, Exercise
from src.workouts.generator import ai_service, rules
from tests.test_training_profile import PROFILE
from tests.test_workout_generator_api import BODY, register, seeded  # noqa: F401

pytestmark = pytest.mark.usefixtures("seeded")

AI_BODY = {
    **BODY,
    "ai_consent": True,
    "consent_version": "gemini-training-v1",
    "preferences": "Prefiro halteres; tenho banco e halteres.",
    "avoid_muscles": ["shoulders"],
    "complaint_details": "Desconforto em movimentos acima da cabeça, já avaliado.",
}


@pytest.fixture
def ready(client, session_factory, monkeypatch):
    register(client)
    assert client.put("/auth/training-profile", json=PROFILE).status_code == 200
    settings = get_settings().model_copy(
        update={
            "GEMINI_API_KEY": SecretStr("fake-key-for-offline-tests"),
            "GEMINI_PERSONAL_DATA_ENABLED": True,
        }
    )
    monkeypatch.setattr(ai_service, "get_settings", lambda: settings)
    baseline = client.post("/workouts/generate", json=BODY).json()
    with session_factory() as session:
        rows = session.scalars(select(Exercise)).all()
        roles = {
            source_id: slot.role
            for slots in ai_service.SLOTS.values()
            for slot in slots
            for source_id in (*slot.candidates, *(slot.beginner_candidates or ()))
        }
        sources = {str(row.id): roles[row.source_id] for row in rows}
    # Uma prescricao curta e valida, diferente do plano-base.
    output = {
        "status": "ready",
        "message": "",
        "name": "Treino personalizado",
        "description": "Plano ajustado às preferências.",
        "days": [
            {
                "name": day["name"],
                "notes": "Mantenha execução controlada.",
                "exercises": [
                    {
                        "exercise_id": day["exercises"][0]["exercise_id"],
                        "role": sources[day["exercises"][0]["exercise_id"]],
                        "sets": 2,
                        "reps_min": 8,
                        "reps_max": 12,
                        "rest_seconds": 60,
                        "notes": "Interrompa se houver dor.",
                    }
                ],
            }
            for day in baseline["days"]
        ],
        "rationale": ["Volume adaptado ao contexto individual [R1]."],
        "warnings": ["Confirme as adaptações com um profissional."],
        "reference_ids": ["R1"],
    }
    return output


def mock_gemini(monkeypatch, output, *, status_code=200, response_body=None, error=None):
    captured = []
    real_client = httpx.Client
    real_call = ai_service._call_gemini
    indices = {}

    def call(context):
        indices.update(
            {item["exercise_id"]: index for index, item in enumerate(context["catalog"])}
        )
        return real_call(context)

    monkeypatch.setattr(ai_service, "_call_gemini", call)

    def handle(request):
        captured.append(request)
        if error is not None:
            raise error
        wire_output = copy.deepcopy(output)
        for day in wire_output.get("days", []):
            for exercise in day["exercises"]:
                if "exercise_id" in exercise:
                    exercise["exercise_index"] = indices.get(
                        exercise.pop("exercise_id"), len(indices)
                    )
        body = (
            response_body
            if response_body is not None
            else {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(wire_output)}]},
                    }
                ]
            }
        )
        return httpx.Response(status_code, json=body)

    monkeypatch.setattr(
        ai_service.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    return captured


def test_ai_final_plan_uses_profile_references_and_questionnaire(client, ready, monkeypatch):
    captured = mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["generator"] == "gemini"
    assert plan["prompt_version"] == ai_service.PROMPT_VERSION
    assert plan["consent_version"] == AI_BODY["consent_version"]
    assert plan["consented_at"] and plan["profile_updated_at"] and plan["model"]
    assert len(plan["days"]) == BODY["days_per_week"]
    assert plan["days"][0]["exercises"][0]["notes"] == "Interrompa se houver dor."
    assert plan["days"][0]["exercises"][0]["name"].startswith("PT ")
    assert {item["id"] for item in plan["references"]} == {"R1", "R3"}
    assert all(item["text"] == rules.REFERENCES[item["id"]] for item in plan["references"])
    volume = Counter()
    for day in plan["days"]:
        seconds = sum(
            rules.SETUP_SECONDS_PER_EXERCISE
            + item["sets"] * (rules.SECONDS_PER_SET + item["rest_seconds"])
            for item in day["exercises"]
        )
        assert day["estimated_minutes"] == rules.WARMUP_MINUTES + math.ceil(seconds / 60)
        for item in day["exercises"]:
            volume[item["muscle_group"]] += item["sets"]
    assert all(item["sets"] == volume[item["muscle"]] for item in plan["weekly_volume"])
    assert client.get("/workouts").json() == []
    request = captured[0]
    assert request.headers["x-goog-api-key"] == "fake-key-for-offline-tests"
    assert "key=" not in str(request.url)
    sent = json.loads(request.content)
    context = json.loads(sent["contents"][0]["parts"][0]["text"])
    assert context["profile"] == PROFILE
    assert context["references"] == rules.REFERENCES
    assert context["goal_rules"]["weekly_sets_major"]
    assert context["questionnaire"]["preferences"] == AI_BODY["preferences"]
    assert context["questionnaire"]["complaint_details"] == AI_BODY["complaint_details"]
    assert context["questionnaire"]["avoid_muscles"] == ["shoulders"]
    assert all(
        "primary_muscles" in item and "secondary_muscles" in item for item in context["catalog"]
    )
    assert "ana@example.com" not in request.content.decode()
    assert "Ana Silva" not in request.content.decode()
    assert "password" not in context and "user_id" not in context
    assert sent["generationConfig"]["responseMimeType"] == "application/json"
    assert sent["generationConfig"]["maxOutputTokens"] == 32768


def test_output_budget_is_configurable_without_retry_or_accepting_truncated_json(
    client, ready, monkeypatch
):
    settings = ai_service.get_settings().model_copy(update={"GEMINI_MAX_OUTPUT_TOKENS": 65536})
    monkeypatch.setattr(ai_service, "get_settings", lambda: settings)
    captured = mock_gemini(
        monkeypatch,
        ready,
        response_body={
            "candidates": [
                {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": json.dumps(ready)}]}}
            ],
            "usageMetadata": {
                "promptTokenCount": 20000,
                "candidatesTokenCount": 5000,
                "thoughtsTokenCount": 60536,
                "private": "do-not-log",
            },
        },
    )
    logs = []
    sink = ai_service.logger.add(lambda message: logs.append(str(message)))
    try:
        response = client.post("/workouts/generate-ai", json=AI_BODY)
    finally:
        ai_service.logger.remove(sink)
    assert response.status_code == 502
    assert "GEMINI_MAX_OUTPUT_TOKENS" in response.json()["detail"]
    assert len(captured) == 1
    assert json.loads(captured[0].content)["generationConfig"]["maxOutputTokens"] == 65536
    text = "\n".join(logs)
    assert "60536" in text and "65536" in text
    assert "do-not-log" not in text and ready["description"] not in text
    assert client.get("/workouts").json() == []


@pytest.mark.parametrize("budget", [0, 11999, 65537])
def test_output_budget_rejects_out_of_range_values(budget):
    with pytest.raises(ValidationError):
        type(get_settings()).model_validate(
            {**get_settings().model_dump(), "GEMINI_MAX_OUTPUT_TOKENS": budget}
        )


@pytest.mark.parametrize("consent", [False, None, "true", 1])
def test_ai_requires_explicit_boolean_consent(client, ready, monkeypatch, consent):
    captured = mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json={**AI_BODY, "ai_consent": consent})
    assert response.status_code == 422
    assert not captured


def test_ai_requires_login_profile_consent_and_config(client, monkeypatch):
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 401
    register(client)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 422
    client.put("/auth/training-profile", json=PROFILE)
    settings = get_settings().model_copy(update={"GEMINI_API_KEY": None})
    monkeypatch.setattr(ai_service, "get_settings", lambda: settings)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 503
    missing = {key: value for key, value in AI_BODY.items() if key != "ai_consent"}
    assert client.post("/workouts/generate-ai", json=missing).status_code == 422
    assert (
        client.post("/workouts/generate-ai", json={**AI_BODY, "consent_version": "old"}).status_code
        == 422
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("unknown_id", "unknown_exercise"),
        ("invalid_role", "schema_validation"),
        ("duplicate", "duplicate_exercise"),
        ("reps", "rep_range"),
        ("sets", "schema_validation"),
        ("days", "day_structure"),
        ("day_name", "day_structure"),
        ("time", "session_duration"),
        ("reference", "references"),
        ("citation", "references"),
        ("title", "plan_content"),
    ],
)
def test_ai_rejects_invalid_plan_without_saving(client, ready, monkeypatch, mutation, reason):
    output = copy.deepcopy(ready)
    exercise = output["days"][0]["exercises"][0]
    if mutation == "unknown_id":
        exercise["exercise_id"] = "00000000-0000-0000-0000-000000000001"
    elif mutation == "invalid_role":
        exercise["role"] = "invented"
    elif mutation == "duplicate":
        output["days"][0]["exercises"].append(copy.deepcopy(exercise))
    elif mutation == "reps":
        exercise["reps_min"] = 20
    elif mutation == "sets":
        exercise["sets"] = 50
    elif mutation == "days":
        output["days"].pop()
    elif mutation == "day_name":
        output["days"][0]["name"] = "Divisão diferente"
    elif mutation == "time":
        # 5 * (40 + 300) + 60 + 8min = 38min; com limite de 30, deve falhar.
        exercise.update(sets=5, rest_seconds=300)
    elif mutation == "reference":
        output["reference_ids"] = ["R999"]
    elif mutation == "citation":
        exercise["notes"] = "Use uma evidência inventada [R999]."
    else:
        output["name"] = ""
    mock_gemini(monkeypatch, output)
    body = {**AI_BODY, "session_minutes": 30} if mutation == "time" else AI_BODY
    response = client.post("/workouts/generate-ai", json=body)
    assert response.status_code == 502, response.text
    assert f"Código: {reason}." in response.json()["detail"]
    assert client.get("/workouts").json() == []


def test_ai_can_request_professional_review_instead_of_a_plan(client, ready, monkeypatch):
    output = {**ready, "status": "needs_professional", "message": "Procure avaliação.", "days": []}
    mock_gemini(monkeypatch, output)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 422
    assert "avaliação" in response.json()["detail"]
    assert client.get("/workouts").json() == []


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 429, 500, 503])
def test_provider_errors_are_explicit_and_do_not_leak_details(client, ready, monkeypatch, status):
    mock_gemini(monkeypatch, ready, status_code=status, response_body={"error": "private-key"})
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 503
    assert f"HTTP {status}" in response.json()["detail"]
    if status != 429:
        assert "cota" not in response.json()["detail"]
    assert "private-key" not in response.text
    assert client.get("/workouts").json() == []


def test_provider_schema_omits_array_bounds_but_local_validation_preserves_them(
    client, ready, monkeypatch, session_factory
):
    with session_factory() as session:
        exercise_ids = [
            str(value) for value in session.scalars(select(Exercise.id).order_by(Exercise.id))
        ]
    schema = ai_service._gemini_response_schema(len(exercise_ids))
    original = ai_service.AiPlan.model_json_schema()
    assert original["properties"]["days"]["maxItems"] == 6
    assert original["$defs"]["AiDay"]["properties"]["exercises"]["minItems"] == 1

    def verify(node):
        if isinstance(node, dict):
            assert "minItems" not in node and "maxItems" not in node
            for value in node.values():
                verify(value)
        elif isinstance(node, list):
            for value in node:
                verify(value)

    verify(schema)
    properties = schema["$defs"]["AiExercise"]["properties"]
    for field, definition in original["$defs"]["AiExercise"]["properties"].items():
        if field != "exercise_id":
            assert properties[field] == definition
    assert "exercise_id" not in properties
    assert properties["exercise_index"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": len(exercise_ids) - 1,
    }
    assert schema["required"] == original["required"]
    assert schema["additionalProperties"] is False
    output = {**ready, "days": ready["days"] * 7}
    captured = mock_gemini(monkeypatch, output)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 502
    assert json.loads(captured[0].content)["generationConfig"]["responseJsonSchema"] == schema
    assert client.get("/workouts").json() == []


def test_local_schema_still_rejects_empty_and_excessive_exercise_lists(ready):
    for exercises in ([], ready["days"][0]["exercises"] * 11):
        output = copy.deepcopy(ready)
        output["days"][0]["exercises"] = exercises
        with pytest.raises(ValidationError):
            ai_service.AiPlan.model_validate(output)


def test_response_schema_limits_ids_to_the_complete_sent_catalog(
    client, ready, monkeypatch, session_factory
):
    with session_factory() as session, session.begin():
        session.add_all(
            Exercise(name=f"Manual schema {index}", muscle_group="chest") for index in range(110)
        )
    captured = mock_gemini(monkeypatch, ready)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 200
    payload = json.loads(captured[0].content)
    context = json.loads(payload["contents"][0]["parts"][0]["text"])
    id_schema = payload["generationConfig"]["responseJsonSchema"]["$defs"]["AiExercise"][
        "properties"
    ]["exercise_index"]
    assert id_schema == {"type": "integer", "minimum": 0, "maximum": len(context["catalog"]) - 1}
    assert len(context["catalog"]) > 100
    assert [item["exercise_index"] for item in context["catalog"]] == list(
        range(len(context["catalog"]))
    )
    assert "enum" not in id_schema


@pytest.mark.parametrize(
    ("index", "reason"),
    [
        (-1, "unknown_exercise"),
        (10**9, "unknown_exercise"),
        (True, "schema_validation"),
        (False, "schema_validation"),
        ("0", "schema_validation"),
        (0.0, "schema_validation"),
        (None, "schema_validation"),
    ],
)
def test_invalid_catalog_indices_are_rejected_without_saving(
    client, ready, monkeypatch, index, reason
):
    output = copy.deepcopy(ready)
    exercise = output["days"][0]["exercises"][0]
    exercise.pop("exercise_id")
    exercise["exercise_index"] = index
    mock_gemini(monkeypatch, output)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 502
    assert f"Código: {reason}." in response.json()["detail"]
    assert client.get("/workouts").json() == []


def test_index_mapping_uses_current_request_order_and_rejects_direct_uuid():
    ids = ["00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000001"]
    output = {"days": [{"exercises": [{"exercise_index": 1}, {"exercise_index": 0}]}]}
    decoded = ai_service._resolve_exercise_indices(output, ids)
    assert [item["exercise_id"] for item in decoded["days"][0]["exercises"]] == [ids[1], ids[0]]
    with pytest.raises(ai_service.AiInvalidResponseError, match="schema_validation"):
        ai_service._resolve_exercise_indices(
            {"days": [{"exercises": [{"exercise_index": 0, "exercise_id": ids[0]}]}]}, ids
        )


def test_catalog_schema_size_does_not_grow_with_uuid_enum():
    small = ai_service._gemini_response_schema(2)
    large = ai_service._gemini_response_schema(5000)
    assert len(json.dumps(large)) - len(json.dumps(small)) == 3
    assert large["$defs"]["AiExercise"]["properties"]["exercise_index"]["maximum"] == 4999


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "response_envelope"),
        ({"candidates": []}, "candidate_count"),
        ({"candidates": [{"finishReason": "MAX_TOKENS"}]}, "token_limit"),
        ({"candidates": [{"finishReason": "SAFETY"}]}, "generation_incomplete"),
        (
            {"candidates": [{"finishReason": "STOP", "content": {"parts": [None]}}]},
            "response_envelope",
        ),
        (
            {
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}
                ]
            },
            "schema_validation",
        ),
    ],
)
def test_blocked_truncated_and_malformed_outputs_are_rejected(
    client, ready, monkeypatch, body, reason
):
    mock_gemini(monkeypatch, ready, response_body=body)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 502
    assert f"Código: {reason}." in response.json()["detail"]


def test_validation_logs_only_known_fields_and_never_response_values(client, ready, monkeypatch):
    output = copy.deepcopy(ready)
    output["private-field@example.com"] = "private-response-value"
    output["days"][0]["exercises"][0]["sets"] = "private-invalid-value"
    mock_gemini(monkeypatch, output)
    logs = []
    sink = ai_service.logger.add(lambda message: logs.append(str(message)))
    try:
        response = client.post("/workouts/generate-ai", json=AI_BODY)
    finally:
        ai_service.logger.remove(sink)
    assert response.status_code == 502
    text = "\n".join(logs) + response.text
    assert "schema_validation" in text
    assert "sets" in text
    for private in (
        "private-field@example.com",
        "private-response-value",
        "private-invalid-value",
        "fake-key-for-offline-tests",
    ):
        assert private not in text


def test_timeout_does_not_fall_back_to_rules(client, ready, monkeypatch):
    mock_gemini(monkeypatch, ready, error=httpx.ReadTimeout("private request"))
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 503
    assert "private request" not in response.text


def test_admin_must_enable_personal_data_before_any_provider_request(client, ready, monkeypatch):
    settings = ai_service.get_settings().model_copy(update={"GEMINI_PERSONAL_DATA_ENABLED": False})
    monkeypatch.setattr(ai_service, "get_settings", lambda: settings)
    captured = mock_gemini(monkeypatch, ready)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 503
    assert not captured


def test_oversized_provider_output_is_rejected(client, ready, monkeypatch):
    mock_gemini(
        monkeypatch, ready, response_body={"large": "x" * (ai_service.MAX_RESPONSE_BYTES + 1)}
    )
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 502


def test_missing_catalog_level_keeps_beginner_compatibility(
    client, ready, monkeypatch, session_factory
):
    exercise_id = ready["days"][0]["exercises"][0]["exercise_id"]
    with session_factory() as session:
        row = session.get(Exercise, UUID(exercise_id))
        row.level = None
        session.commit()
    captured = mock_gemini(monkeypatch, ready)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 200
    context = json.loads(json.loads(captured[0].content)["contents"][0]["parts"][0]["text"])
    assert exercise_id in {entry["exercise_id"] for entry in context["catalog"]}


def test_all_enabled_accessible_exercises_are_sent_without_curated_or_level_filter(
    client, ready, monkeypatch, session_factory
):
    user_id = UUID(client.get("/auth/me").json()["id"])
    with session_factory() as session:
        other = User(name="Outro", email="private@example.com", password_hash="unused")
        session.add(other)
        session.flush()
        additions = [
            Exercise(name="Manual", muscle_group="forearms", owner_user_id=user_id),
            Exercise(
                name="Global avançado",
                muscle_group="neck",
                source="other",
                source_id="uncurated",
                level="expert",
                category="stretching",
            ),
            Exercise(name="Privado", muscle_group="chest", owner_user_id=other.id),
            Exercise(
                name="Outra fonte", muscle_group="chest", source="second", source_id="uncurated"
            ),
        ]
        session.add_all(additions)
        session.flush()
        visible_ids = {str(item.id) for item in additions if item.owner_user_id != other.id}
        private_id = str(additions[2].id)
        expert_id = str(
            session.scalar(select(Exercise.id).where(Exercise.source_id == "Hanging_Leg_Raise"))
        )
        session.commit()
    captured = mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json={**AI_BODY, "level": "beginner"})
    assert response.status_code == 200
    context = json.loads(json.loads(captured[0].content)["contents"][0]["parts"][0]["text"])
    ids = {item["exercise_id"] for item in context["catalog"]}
    payload = json.loads(captured[0].content)
    index_schema = payload["generationConfig"]["responseJsonSchema"]["$defs"]["AiExercise"][
        "properties"
    ]["exercise_index"]
    assert index_schema["maximum"] == len(ids) - 1
    assert visible_ids <= ids
    assert expert_id in ids and private_id not in ids
    assert len(ids) == len(context["catalog"])


def test_disabled_exercise_is_not_sent_and_cannot_be_returned(client, ready, monkeypatch):
    exercise_id = ready["days"][0]["exercises"][0]["exercise_id"]
    assert (
        client.put(f"/exercises/{exercise_id}/ai-availability", json={"enabled": False}).status_code
        == 204
    )
    captured = mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 502
    context = json.loads(json.loads(captured[0].content)["contents"][0]["parts"][0]["text"])
    assert exercise_id not in {item["exercise_id"] for item in context["catalog"]}
    payload = json.loads(captured[0].content)
    assert (
        payload["generationConfig"]["responseJsonSchema"]["$defs"]["AiExercise"]["properties"][
            "exercise_index"
        ]["maximum"]
        == len(context["catalog"]) - 1
    )


def test_empty_enabled_catalog_stops_before_gemini(client, ready, monkeypatch, session_factory):
    user_id = UUID(client.get("/auth/me").json()["id"])
    with session_factory() as session:
        for exercise_id in session.scalars(select(Exercise.id)).all():
            session.add(DisabledExercise(user_id=user_id, exercise_id=exercise_id))
        session.commit()
    captured = mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 422 and "habilitado" in response.json()["detail"]
    assert not captured


def test_catalog_is_complete_beyond_page_size(client, ready, monkeypatch, session_factory):
    with session_factory() as session:
        rows = [Exercise(name=f"Extra {index}", muscle_group="chest") for index in range(125)]
        session.add_all(rows)
        session.flush()
        ids = {str(row.id) for row in rows}
        session.commit()
    captured = mock_gemini(monkeypatch, ready)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 200
    context = json.loads(json.loads(captured[0].content)["contents"][0]["parts"][0]["text"])
    assert ids <= {item["exercise_id"] for item in context["catalog"]}


def test_disabling_during_generation_rejects_response(client, ready, monkeypatch, session_factory):
    user_id = UUID(client.get("/auth/me").json()["id"])
    exercise_id = UUID(ready["days"][0]["exercises"][0]["exercise_id"])

    def generate_and_disable(context):
        with session_factory() as session:
            session.add(DisabledExercise(user_id=user_id, exercise_id=exercise_id))
            session.commit()
        return ai_service.AiPlan.model_validate(ready)

    monkeypatch.setattr(ai_service, "_call_gemini", generate_and_disable)
    assert client.post("/workouts/generate-ai", json=AI_BODY).status_code == 502


def test_manual_only_catalog_can_generate_without_curated_baseline(
    client, ready, monkeypatch, session_factory
):
    user_id = UUID(client.get("/auth/me").json()["id"])
    with session_factory() as session:
        for exercise_id in session.scalars(select(Exercise.id)).all():
            session.add(DisabledExercise(user_id=user_id, exercise_id=exercise_id))
        manual = Exercise(
            name="Manual exclusivo",
            muscle_group="forearms",
            owner_user_id=user_id,
            level="expert",
        )
        session.add(manual)
        session.flush()
        manual_id = str(manual.id)
        session.commit()
    output = copy.deepcopy(ready)
    for day in output["days"]:
        day["exercises"][0].update(exercise_id=manual_id, role="isolation")
    captured = mock_gemini(monkeypatch, output)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["days"][0]["exercises"][0]["exercise_id"] == manual_id
    assert response.json()["days"][0]["exercises"][0]["name"] == "Manual exclusivo"
    assert (
        next(item for item in response.json()["weekly_volume"] if item["muscle"] == "forearms")[
            "target"
        ]
        == 0
    )
    context = json.loads(json.loads(captured[0].content)["contents"][0]["parts"][0]["text"])
    assert [item["exercise_id"] for item in context["catalog"]] == [manual_id]


def test_final_plan_can_be_saved_with_notes_and_ai_metadata(client, ready, monkeypatch):
    mock_gemini(monkeypatch, ready)
    response = client.post("/workouts/generate-ai", json=AI_BODY)
    assert response.status_code == 200
    plan = response.json()
    metadata_keys = {
        "generator",
        "model",
        "prompt_version",
        "rules_version",
        "review_status",
        "rationale",
        "warnings",
        "references",
        "weekly_volume",
        "consent_version",
        "consented_at",
        "profile_updated_at",
    }
    body = {
        "name": plan["name"],
        "description": plan["description"],
        "goal": plan["goal"],
        "level": plan["level"],
        "source": "ai",
        "ai_metadata": {key: plan[key] for key in metadata_keys},
        "days": [
            {
                "name": day["name"],
                "notes": day["notes"],
                "exercises": [
                    {
                        key: item[key]
                        for key in (
                            "exercise_id",
                            "sets",
                            "reps_min",
                            "reps_max",
                            "rest_seconds",
                            "notes",
                        )
                    }
                    for item in day["exercises"]
                ],
            }
            for day in plan["days"]
        ],
    }
    saved = client.post("/workouts", json=body)
    assert saved.status_code == 201, saved.text
    assert saved.json()["ai_metadata"]["generator"] == "gemini"
    assert saved.json()["days"][0]["exercises"][0]["notes"] == "Interrompa se houver dor."
    assert re.search(r"\[R3\]", saved.json()["description"])
