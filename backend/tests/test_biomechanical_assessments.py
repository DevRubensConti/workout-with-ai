import importlib.util
import io
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from src.auth.models import User
from src.workouts.biomechanics.models import (
    BiomechanicalAssessmentReview,
    BiomechanicalScaleVersion,
    ExerciseBiomechanicalAssessment,
    ExerciseRegionDemand,
)
from src.workouts.exercises.models import Exercise, ExerciseTranslation

ENDPOINT = "/biomechanical-assessments"
REGIONS = ("shoulder", "lumbar_spine", "cervical_spine", "knee", "elbow")


def load_migration(filename):
    path = Path(__file__).parents[1] / "migrations" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def catalog(session_factory):
    initial = load_migration("0012_biomechanical_scales.py").INITIAL_DEFINITION
    with session_factory() as session, session.begin():
        session.add_all(
            [
                BiomechanicalScaleVersion(
                    version=1, definition=deepcopy(initial), change_reason="Inicial"
                ),
                BiomechanicalScaleVersion(
                    version=2,
                    definition={**deepcopy(initial), "title": "Escala atual"},
                    change_reason="Nova versão",
                ),
            ]
        )
        owner = User(name="Dono privado", email="private@example.com", password_hash="unused")
        session.add(owner)
        session.flush()
        exercise = Exercise(
            name="Synthetic Press",
            muscle_group="chest",
            source="synthetic",
            source_id="test_press",
            translations=[
                ExerciseTranslation(locale="pt-BR", name="Supino sintético", instructions=[]),
            ],
        )
        private = Exercise(name="Privado", muscle_group="chest", owner_user_id=owner.id)
        session.add_all([exercise, private])
        session.flush()
        return {"exercise_id": exercise.id, "private_id": private.id}


def seed_assessment(
    session_factory,
    exercise_id,
    *,
    missing=False,
    scale_version=1,
    supersedes_id=None,
):
    with session_factory() as session, session.begin():
        assessment = ExerciseBiomechanicalAssessment(
            exercise_id=exercise_id,
            scale_version=scale_version,
            supersedes_id=supersedes_id,
            assessment_method="ai",
            assessment_source="Modelo sintético / prompt v1",
            execution_context="Execução controlada, com apoio, conforme cadastro sintético.",
            regions=[
                ExerciseRegionDemand(
                    region_code=region,
                    assessment_status="unassessed" if index == 4 else "assessed",
                    demand_score=None if index == 4 else index,
                    demand_role=None if index == 4 else "stabilizing",
                    justification="Dados insuficientes."
                    if index == 4
                    else "Justificativa sintética.",
                )
                for index, region in enumerate(REGIONS[:4] if missing else REGIONS)
            ],
        )
        session.add(assessment)
        session.flush()
        return assessment.id


@pytest.fixture()
def assessment_id(session_factory, catalog):
    return seed_assessment(session_factory, catalog["exercise_id"])


def login(client, session_factory, *, admin=True):
    response = client.post(
        "/auth/register",
        json={
            "name": "Revisor",
            "email": "review@example.com",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    user_id = UUID(response.json()["id"])
    if admin:
        with session_factory() as session, session.begin():
            user = session.get(User, user_id)
            assert user is not None
            user.role = "admin"
    return user_id


def decision(value="reviewed"):
    return {
        "decision": value,
        "notes": "Dados conferidos segundo a escala vinculada.",
        "content_hash": "0" * 64,
    }


def review_body(client, assessment_id, value="reviewed"):
    return {
        **decision(value),
        "content_hash": client.get(f"{ENDPOINT}/{assessment_id}").json()["content_hash"],
    }


def test_admin_only(client, session_factory, assessment_id):
    path = f"{ENDPOINT}/{assessment_id}"
    assert client.get(ENDPOINT).status_code == 401
    assert client.get(path).status_code == 401
    assert client.post(f"{path}/review", json=decision()).status_code == 401
    login(client, session_factory, admin=False)
    assert client.get(ENDPOINT).status_code == 403
    assert client.get(path).status_code == 403
    assert client.post(f"{path}/review", json=decision()).status_code == 403


def test_list_search_filters_history_and_private_exclusion(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    login(client, session_factory)
    newer_id = seed_assessment(
        session_factory, catalog["exercise_id"], scale_version=2, supersedes_id=assessment_id
    )
    private_id = seed_assessment(session_factory, catalog["private_id"])
    response = client.get(ENDPOINT, params={"q": "SUPINO", "page_size": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2 and data["total_pages"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["exercise_name"] == "Supino sintético"
    assert client.get(ENDPOINT, params={"q": "test_press"}).json()["total"] == 2
    assert client.get(ENDPOINT, params={"q": "Synthetic Press"}).json()["total"] == 2
    assert client.get(ENDPOINT, params={"q": "%"}).json()["total"] == 0
    assert client.get(ENDPOINT, params={"q": "_"}).json()["total"] == 2
    assert client.get(ENDPOINT, params={"q": "_missing"}).json()["total"] == 0
    assert client.get(ENDPOINT, params={"page": 2, "page_size": 1}).json()["page"] == 2
    assert client.get(ENDPOINT, params={"exercise_id": str(uuid4())}).json()["total"] == 0
    assert (
        client.get(ENDPOINT, params={"exercise_id": str(catalog["exercise_id"])}).json()["total"]
        == 2
    )
    assert client.get(f"{ENDPOINT}/{private_id}").status_code == 404
    assert client.post(f"{ENDPOINT}/{private_id}/review", json=decision()).status_code == 404
    assert client.get(f"{ENDPOINT}/{newer_id}").json()["supersedes_id"] == str(assessment_id)


def test_detail_uses_historical_scale_and_distinguishes_zero_from_unknown(
    client,
    session_factory,
    assessment_id,
):
    login(client, session_factory)
    detail = client.get(f"{ENDPOINT}/{assessment_id}").json()
    assert detail["review_status"] == "pending"
    assert detail["review"] is None
    assert detail["validation_errors"] == []
    assert detail["scale_version"] == detail["scale"]["version"] == 1
    assert detail["uses_current_scale"] is False
    assert detail["scale"]["definition"]["title"] == "Escala de Demanda Biomecânica Regional"
    assert len(detail["regions"]) == 5
    by_code = {item["region_code"]: item for item in detail["regions"]}
    assert by_code["shoulder"]["demand_score"] == 0
    assert by_code["elbow"]["demand_score"] is None
    assert by_code["elbow"]["demand_role"] is None
    assert by_code["elbow"]["assessment_status"] == "unassessed"


def test_list_previews_use_historical_labels_and_preserve_zero_unknown_and_missing(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    login(client, session_factory)
    with session_factory() as session, session.begin():
        scale = session.get(BiomechanicalScaleVersion, 1)
        definition = deepcopy(scale.definition)
        definition["regions"][0]["label"] = "Região histórica"
        scale.definition = definition
    data = client.get(ENDPOINT).json()
    preview = {entry["region_code"]: entry for entry in data["items"][0]["region_scores"]}
    assert len(preview) == 5
    assert preview[definition["regions"][0]["code"]]["label"] == "Região histórica"
    assert preview["shoulder"]["demand_score"] == 0
    assert preview["shoulder"]["assessment_status"] == "assessed"
    assert preview["elbow"]["demand_score"] is None
    assert preview["elbow"]["assessment_status"] == "unassessed"
    missing_id = seed_assessment(session_factory, catalog["exercise_id"], missing=True)
    missing = client.get(ENDPOINT, params={"page_size": 1}).json()["items"][0]
    assert missing["id"] == str(missing_id)
    elbow = next(entry for entry in missing["region_scores"] if entry["region_code"] == "elbow")
    assert elbow["demand_score"] is None and elbow["assessment_status"] is None


def test_global_counts_use_latest_assessment_and_ignore_filters(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    login(client, session_factory)
    without_assessment = None
    with session_factory() as session, session.begin():
        without_assessment = Exercise(name="Sem avaliação", muscle_group="chest")
        session.add(without_assessment)
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=assessment_id,
                decision="reviewed",
                notes="Conferido",
            )
        )
    seed_assessment(session_factory, catalog["private_id"])
    expected = {"total_exercises": 2, "validated_exercises": 1, "unvalidated_exercises": 1}
    for params in [
        {},
        {"q": "não existe"},
        {"review_status": "pending"},
        {"page": 2},
        {"exercise_id": str(catalog["private_id"])},
    ]:
        response = client.get(ENDPOINT, params=params)
        assert response.status_code == 200, response.text
        assert response.json()["counts"] == expected

    newer_id = seed_assessment(
        session_factory,
        catalog["exercise_id"],
        supersedes_id=assessment_id,
    )
    expected = {"total_exercises": 2, "validated_exercises": 0, "unvalidated_exercises": 2}
    assert client.get(ENDPOINT).json()["counts"] == expected
    assert (
        client.post(
            f"{ENDPOINT}/{newer_id}/review",
            json=review_body(client, newer_id, "rejected"),
        ).status_code
        == 200
    )
    assert client.get(ENDPOINT).json()["counts"] == expected

    latest = seed_assessment(session_factory, catalog["exercise_id"], supersedes_id=newer_id)
    assert (
        client.post(
            f"{ENDPOINT}/{latest}/review",
            json=review_body(client, latest),
        ).status_code
        == 200
    )
    assert client.get(ENDPOINT).json()["counts"] == {
        "total_exercises": 2,
        "validated_exercises": 1,
        "unvalidated_exercises": 1,
    }


def test_global_counts_break_timestamp_ties_by_id_and_not_review_time(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    login(client, session_factory)
    other_id = seed_assessment(session_factory, catalog["exercise_id"])
    lower, higher = sorted([assessment_id, other_id])
    with session_factory() as session, session.begin():
        earlier = session.get(ExerciseBiomechanicalAssessment, lower)
        later = session.get(ExerciseBiomechanicalAssessment, higher)
        later.created_at = earlier.created_at
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=lower,
                decision="reviewed",
                notes="Histórica",
                reviewed_at=earlier.created_at + timedelta(days=1),
            )
        )
    data = client.get(ENDPOINT).json()
    assert data["items"][0]["id"] == str(higher)
    assert data["counts"] == {
        "total_exercises": 1,
        "validated_exercises": 0,
        "unvalidated_exercises": 1,
    }
    with session_factory() as session, session.begin():
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=higher,
                decision="reviewed",
                notes="Atual",
            )
        )
    assert client.get(ENDPOINT).json()["counts"]["validated_exercises"] == 1


def test_empty_catalog_counts_are_zero(client, session_factory):
    login(client, session_factory)
    result = client.get(ENDPOINT)
    assert result.status_code == 200
    assert result.json()["counts"] == {
        "total_exercises": 0,
        "validated_exercises": 0,
        "unvalidated_exercises": 0,
    }
    assert result.json()["items"] == []


def correction_body(client, assessment_id):
    detail = client.get(f"{ENDPOINT}/{assessment_id}").json()
    regions = deepcopy(detail["regions"])
    regions[0]["justification"] = "Justificativa corrigida após análise manual."
    return {
        "content_hash": detail["content_hash"],
        "reason": "Revisão das notas e da execução.",
        "regions": regions,
    }


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"category": "stretching"}, ["stretch-chest", "stretch-legs"]),
        ({"muscle_group": "chest"}, ["strength-chest", "stretch-chest"]),
        ({"category": "stretching", "muscle_group": "chest"}, ["stretch-chest"]),
        ({"category": "strength", "muscle_group": "quadriceps"}, []),
        ({"category": "unknown"}, []),
    ],
)
def test_assessment_category_and_muscle_filters(
    client,
    session_factory,
    catalog,
    filters,
    expected,
):
    login(client, session_factory)
    ids = {}
    with session_factory() as session, session.begin():
        session.get(Exercise, catalog["private_id"]).muscle_group = "private-only"
        for name, category, muscle in (
            ("stretch-chest", "stretching", "chest"),
            ("stretch-legs", "stretching", "quadriceps"),
            ("strength-chest", "strength", "chest"),
        ):
            exercise = Exercise(name=name, category=category, muscle_group=muscle)
            session.add(exercise)
            session.flush()
            ids[name] = exercise.id
    for exercise_id in ids.values():
        seed_assessment(session_factory, exercise_id)
    baseline = client.get(ENDPOINT).json()
    result = client.get(ENDPOINT, params={**filters, "review_status": "pending"})
    assert result.status_code == 200, result.text
    data = result.json()
    assert sorted(item["exercise_name"] for item in data["items"]) == sorted(expected)
    assert data["total"] == len(expected)
    assert data["counts"] == baseline["counts"]
    assert data["filters"] == {
        "categories": ["strength", "stretching"],
        "muscle_groups": ["chest", "quadriceps"],
    }
    if expected:
        paged = client.get(ENDPOINT, params={**filters, "page_size": 1}).json()
        assert paged["total"] == len(expected)
        assert len(paged["items"]) == 1
        searched = client.get(ENDPOINT, params={**filters, "q": expected[0]}).json()
        assert [item["exercise_name"] for item in searched["items"]] == [expected[0]]


def test_images_in_list_and_detail(client, session_factory, catalog, assessment_id):
    login(client, session_factory)
    with session_factory() as session, session.begin():
        exercise = session.get(Exercise, catalog["exercise_id"])
        exercise.images = ["Synthetic/0.jpg", "Synthetic/1.jpg"]
    expected = ["Synthetic/0.jpg", "Synthetic/1.jpg"]
    assert client.get(ENDPOINT).json()["items"][0]["images"] == expected
    assert client.get(f"{ENDPOINT}/{assessment_id}").json()["images"] == expected
    with session_factory() as session, session.begin():
        session.get(Exercise, catalog["exercise_id"]).images = None
    assert client.get(f"{ENDPOINT}/{assessment_id}").json()["images"] == []


@pytest.mark.parametrize("decision_status", ["pending", "reviewed", "rejected"])
def test_correction_creates_pending_version_and_preserves_original(
    client,
    session_factory,
    assessment_id,
    decision_status,
):
    user_id = login(client, session_factory)
    if decision_status != "pending":
        assert (
            client.post(
                f"{ENDPOINT}/{assessment_id}/review",
                json=review_body(client, assessment_id, decision_status),
            ).status_code
            == 200
        )
    before = client.get(f"{ENDPOINT}/{assessment_id}").json()
    body = correction_body(client, assessment_id)
    body["regions"][0].update(
        assessment_status="assessed",
        demand_score=5,
        demand_role="direct",
    )
    response = client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["id"] != str(assessment_id)
    assert result["supersedes_id"] == str(assessment_id)
    assert result["scale_version"] == before["scale_version"]
    assert result["execution_context"] == before["execution_context"]
    assert result["created_by"] == str(user_id)
    assert result["assessment_method"] == "manual"
    assert body["reason"] in result["assessment_source"]
    assert result["review_status"] == "pending" and result["review"] is None
    assert result["validation_errors"] == []
    assert result["regions"] == sorted(body["regions"], key=lambda region: region["region_code"])
    original = client.get(f"{ENDPOINT}/{assessment_id}").json()
    if decision_status == "pending":
        assert original["review_status"] == "rejected"
        assert original["review"]["decision"] == "rejected"
        assert original["review"]["reviewed_by"] == str(user_id)
        assert "automaticamente" in original["review"]["notes"]
        assert {k: v for k, v in original.items() if k not in ("review", "review_status")} == {
            k: v for k, v in before.items() if k not in ("review", "review_status")
        }
    else:
        assert original == before
    listing = client.get(ENDPOINT).json()
    assert listing["items"][0]["id"] == result["id"]
    assert listing["counts"]["validated_exercises"] == 0
    assert listing["counts"]["unvalidated_exercises"] == 1
    pending = client.get(ENDPOINT, params={"review_status": "pending"}).json()["items"]
    assert [item["id"] for item in pending] == [result["id"]]
    assert (
        client.post(
            f"{ENDPOINT}/{result['id']}/review",
            json=review_body(client, result["id"]),
        ).status_code
        == 200
    )
    assert client.get(ENDPOINT).json()["counts"]["validated_exercises"] == 1


def test_correction_conflicts_for_changed_or_superseded_source(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    login(client, session_factory)
    body = correction_body(client, assessment_id)
    assert (
        client.post(
            f"{ENDPOINT}/{assessment_id}/corrections",
            json={**body, "content_hash": "0" * 64},
        ).status_code
        == 409
    )
    seed_assessment(session_factory, catalog["exercise_id"], supersedes_id=assessment_id)
    assert client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body).status_code == 409
    assert client.get(f"{ENDPOINT}/{assessment_id}").json()["review_status"] == "pending"


def test_failed_correction_rolls_back_automatic_rejection(
    client,
    session_factory,
    assessment_id,
    monkeypatch,
):
    from sqlalchemy.orm import Session

    login(client, session_factory)
    body = correction_body(client, assessment_id)
    before = client.get(f"{ENDPOINT}/{assessment_id}").json()

    def failing_commit(session):
        session.flush()
        raise IntegrityError("Simulated correction failure", {}, Exception("Test failure"))

    monkeypatch.setattr(Session, "commit", failing_commit)
    response = client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body)
    assert response.status_code == 409, response.text
    assert client.get(f"{ENDPOINT}/{assessment_id}").json() == before
    assert client.get(ENDPOINT).json()["total"] == 1


def test_correction_rejects_unchanged_and_double_submit(client, session_factory, assessment_id):
    login(client, session_factory)
    body = correction_body(client, assessment_id)
    detail = client.get(f"{ENDPOINT}/{assessment_id}").json()
    assert (
        client.post(
            f"{ENDPOINT}/{assessment_id}/corrections",
            json={**body, "regions": detail["regions"]},
        ).status_code
        == 422
    )
    assert client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body).status_code == 201
    assert client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body).status_code == 409


@pytest.mark.parametrize(
    "invalid",
    [
        "score",
        "boolean_score",
        "missing_role",
        "unassessed_with_score",
        "duplicate_region",
        "missing_region",
        "long_reason",
        "long_justification",
    ],
)
def test_correction_validates_all_five_regions(
    client,
    session_factory,
    assessment_id,
    invalid,
):
    login(client, session_factory)
    body = correction_body(client, assessment_id)
    if invalid == "score":
        body["regions"][0]["demand_score"] = 6
    elif invalid == "boolean_score":
        body["regions"][0]["demand_score"] = True
    elif invalid == "missing_role":
        body["regions"][0].update(assessment_status="assessed", demand_score=1, demand_role=None)
    elif invalid == "unassessed_with_score":
        body["regions"][0].update(assessment_status="unassessed", demand_score=1)
    elif invalid == "duplicate_region":
        body["regions"][0] = body["regions"][1]
    elif invalid == "missing_region":
        body["regions"].pop()
    elif invalid == "long_reason":
        body["reason"] = "a" * 401
    else:
        body["regions"][0]["justification"] = "a" * 4001
    assert client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body).status_code == 422
    assert client.get(ENDPOINT).json()["total"] == 1


def test_correction_accepts_zero_and_unassessed_and_repairs_missing_regions(
    client,
    session_factory,
    catalog,
):
    login(client, session_factory)
    source_id = seed_assessment(session_factory, catalog["exercise_id"], missing=True)
    body = correction_body(client, source_id)
    body["regions"].append(
        {
            "region_code": "elbow",
            "assessment_status": "unassessed",
            "demand_score": None,
            "demand_role": None,
            "justification": "Informação insuficiente.",
        }
    )
    response = client.post(f"{ENDPOINT}/{source_id}/corrections", json=body)
    assert response.status_code == 201, response.text
    regions = {region["region_code"]: region for region in response.json()["regions"]}
    assert regions["shoulder"]["demand_score"] == 0
    assert regions["elbow"]["demand_score"] is None


def test_corrections_require_admin_and_exclude_private_catalog(
    client,
    session_factory,
    catalog,
    assessment_id,
):
    path = f"{ENDPOINT}/{assessment_id}/corrections"
    assert client.post(path, json={}).status_code == 401
    user_id = login(client, session_factory, admin=False)
    assert client.post(path, json={}).status_code == 403
    with session_factory() as session, session.begin():
        session.get(User, user_id).role = "admin"
    body = correction_body(client, assessment_id)
    private_id = seed_assessment(session_factory, catalog["private_id"])
    assert client.post(f"{ENDPOINT}/{private_id}/corrections", json=body).status_code == 404
    assert client.post(f"{ENDPOINT}/{uuid4()}/corrections", json=body).status_code == 404


@pytest.mark.parametrize("outcome", ["reviewed", "rejected"])
def test_review_is_audited_final_and_does_not_change_results(
    client,
    session_factory,
    assessment_id,
    outcome,
):
    reviewer_id = login(client, session_factory)
    path = f"{ENDPOINT}/{assessment_id}"
    before = client.get(path).json()
    response = client.post(f"{path}/review", json=review_body(client, assessment_id, outcome))
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["review_status"] == outcome
    assert detail["regions"] == before["regions"]
    assert detail["scale"] == before["scale"]
    assert detail["review"]["decision"] == outcome
    assert detail["review"]["reviewed_by"] == str(reviewer_id)
    assert detail["review"]["reviewed_at"]
    assert client.get(path).json() == detail
    assert client.get(ENDPOINT, params={"review_status": "pending"}).json()["total"] == 0
    assert client.get(ENDPOINT, params={"review_status": outcome}).json()["total"] == 1
    assert client.post(f"{path}/review", json=decision()).status_code == 409
    assert client.get(path).json()["review"] == detail["review"]
    assert client.put(path, json={}).status_code == 405
    assert client.delete(path).status_code == 405
    assert client.post(ENDPOINT, json={}).status_code == 405


def test_incomplete_import_cannot_be_accepted_but_can_be_rejected(
    client,
    session_factory,
    catalog,
):
    login(client, session_factory)
    assessment_id = seed_assessment(session_factory, catalog["exercise_id"], missing=True)
    path = f"{ENDPOINT}/{assessment_id}"
    assert client.get(path).json()["validation_errors"]
    assert client.post(f"{path}/review", json=review_body(client, assessment_id)).status_code == 422
    assert client.get(path).json()["review_status"] == "pending"
    assert (
        client.post(
            f"{path}/review", json=review_body(client, assessment_id, "rejected")
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "pending", "notes": "Justificativa"},
        {"decision": "reviewed", "notes": "a" * 4001},
        {"decision": "reviewed", "notes": "Justificativa", "reviewed_by": str(uuid4())},
    ],
)
def test_invalid_review_rejected(client, session_factory, assessment_id, body):
    login(client, session_factory)
    assert (
        client.post(
            f"{ENDPOINT}/{assessment_id}/review", json={"content_hash": "0" * 64, **body}
        ).status_code
        == 422
    )


def test_review_requires_content_hash(client, session_factory, assessment_id):
    login(client, session_factory)
    body = decision()
    del body["content_hash"]
    assert client.post(f"{ENDPOINT}/{assessment_id}/review", json=body).status_code == 422


@pytest.mark.parametrize("text", [None, "", "   "])
@pytest.mark.parametrize("outcome", ["reviewed", "rejected"])
def test_review_accepts_optional_justifications(
    client,
    session_factory,
    assessment_id,
    text,
    outcome,
):
    login(client, session_factory)
    with session_factory() as session, session.begin():
        assessment = session.get(ExerciseBiomechanicalAssessment, assessment_id)
        for region in assessment.regions:
            region.justification = ""
    detail = client.get(f"{ENDPOINT}/{assessment_id}").json()
    assert detail["validation_errors"] == []
    body = {"decision": outcome, "content_hash": detail["content_hash"]}
    if text is not None:
        body["notes"] = text
    response = client.post(f"{ENDPOINT}/{assessment_id}/review", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["review"]["notes"] == ""
    assert response.json()["review_status"] == outcome
    assert client.get(f"{ENDPOINT}/{assessment_id}").json()["review"]["notes"] == ""


@pytest.mark.parametrize("text", [None, "", "   "])
def test_correction_accepts_optional_reason_and_region_justifications(
    client,
    session_factory,
    assessment_id,
    text,
):
    login(client, session_factory)
    before = client.get(f"{ENDPOINT}/{assessment_id}").json()
    body = correction_body(client, assessment_id)
    body.pop("reason")
    for region in body["regions"]:
        region.pop("justification")
        if text is not None:
            region["justification"] = text
    if text is not None:
        body["reason"] = text
    response = client.post(f"{ENDPOINT}/{assessment_id}/corrections", json=body)
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["assessment_source"] == "Correção administrativa"
    assert detail["validation_errors"] == []
    assert all(region["justification"] == "" for region in detail["regions"])
    original = client.get(f"{ENDPOINT}/{assessment_id}").json()
    assert original["review_status"] == "rejected"
    assert original["regions"] == before["regions"]
    assert original["content_hash"] == before["content_hash"]
    review = client.post(
        f"{ENDPOINT}/{detail['id']}/review",
        json={
            "decision": "reviewed",
            "content_hash": detail["content_hash"],
        },
    )
    assert review.status_code == 200, review.text


def test_missing_assessment_and_invalid_filters(client, session_factory):
    login(client, session_factory)
    assert client.get(f"{ENDPOINT}/{uuid4()}").status_code == 404
    assert client.post(f"{ENDPOINT}/{uuid4()}/review", json=decision()).status_code == 404
    for params in (
        {"page": 0},
        {"page_size": 101},
        {"review_status": "bad"},
        {"exercise_id": "bad"},
    ):
        assert client.get(ENDPOINT, params=params).status_code == 422
    assert client.get(ENDPOINT).json()["total"] == 0


def test_external_changes_require_reloading_before_review(client, session_factory, assessment_id):
    login(client, session_factory)
    body = review_body(client, assessment_id)
    with session_factory() as session, session.begin():
        region = session.get(ExerciseRegionDemand, (assessment_id, "shoulder"))
        assert region is not None
        region.demand_score = 3
    assert client.post(f"{ENDPOINT}/{assessment_id}/review", json=body).status_code == 409
    assert client.get(f"{ENDPOINT}/{assessment_id}").json()["review_status"] == "pending"
    assert (
        client.post(
            f"{ENDPOINT}/{assessment_id}/review", json=review_body(client, assessment_id)
        ).status_code
        == 200
    )


def test_concurrent_review_keeps_winning_decision(
    client,
    session_factory,
    assessment_id,
    monkeypatch,
):
    from sqlalchemy.orm import Session

    reviewer_id = login(client, session_factory)
    body = review_body(client, assessment_id)
    original_commit = Session.commit
    inserted = False

    def competing_commit(session):
        nonlocal inserted
        if not inserted and any(
            isinstance(row, BiomechanicalAssessmentReview) for row in session.new
        ):
            inserted = True
            with session_factory() as competing:
                competing.add(
                    BiomechanicalAssessmentReview(
                        assessment_id=assessment_id,
                        decision="rejected",
                        notes="Decisão concorrente.",
                        reviewed_by=reviewer_id,
                    )
                )
                original_commit(competing)
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", competing_commit)
    assert client.post(f"{ENDPOINT}/{assessment_id}/review", json=body).status_code == 409
    detail = client.get(f"{ENDPOINT}/{assessment_id}").json()
    assert detail["review_status"] == "rejected"
    assert detail["review"]["notes"] == "Decisão concorrente."


@pytest.mark.parametrize(
    "score,role,status",
    [
        (6, "direct", "assessed"),
        (-1, "direct", "assessed"),
        (None, "direct", "assessed"),
        (2, None, "assessed"),
        (1, "invalid", "assessed"),
        (0, None, "unassessed"),
        (None, "direct", "unassessed"),
        (None, None, "unknown"),
    ],
)
def test_database_rejects_invalid_region_results(
    session_factory,
    assessment_id,
    score,
    role,
    status,
):
    with session_factory() as session:
        region = session.get(ExerciseRegionDemand, (assessment_id, "shoulder"))
        region.demand_score, region.demand_role, region.assessment_status = score, role, status
        with pytest.raises(IntegrityError):
            session.commit()


def test_database_restricts_references_and_duplicate_reviews(
    session_factory, assessment_id, catalog
):
    with session_factory() as session:
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=assessment_id,
                decision="reviewed",
                notes="Conferido",
            )
        )
        session.commit()
    with session_factory() as session:
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=assessment_id,
                decision="rejected",
                notes="Outra decisão",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    with session_factory() as session:
        exercise = session.get(Exercise, catalog["exercise_id"])
        session.delete(exercise)
        with pytest.raises(IntegrityError):
            session.commit()
    with session_factory() as session:
        scale = session.get(BiomechanicalScaleVersion, 1)
        session.delete(scale)
        with pytest.raises(IntegrityError):
            session.commit()
    with session_factory() as session:
        invalid = ExerciseBiomechanicalAssessment(
            exercise_id=catalog["private_id"],
            supersedes_id=assessment_id,
            scale_version=1,
            assessment_method="manual",
            assessment_source="Teste",
            execution_context="Teste",
        )
        session.add(invalid)
        with pytest.raises(IntegrityError):
            session.commit()


def test_migration_creates_empty_tables_and_preserves_catalog(monkeypatch):
    migration = load_migration("0013_biomechanical_assessments.py")
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE exercises (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO exercises VALUES ('existing')")
            connection.exec_driver_sql(
                "CREATE TABLE biomechanical_scale_versions (version INTEGER PRIMARY KEY)"
            )
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            for table in (
                "exercise_biomechanical_assessments",
                "exercise_region_demands",
                "biomechanical_assessment_reviews",
            ):
                assert table in inspect(connection).get_table_names()
                assert connection.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar() == 0
            migration.downgrade()
            assert "exercise_region_demands" not in inspect(connection).get_table_names()
            assert connection.exec_driver_sql("SELECT id FROM exercises").scalar() == "existing"
    finally:
        engine.dispose()


def test_postgresql_offline_migration_contains_integrity_guards(monkeypatch):
    migration = load_migration("0013_biomechanical_assessments.py")
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output, "literal_binds": True},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "INSERT INTO" not in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("CREATE CONSTRAINT TRIGGER") == 2
    assert "DEFERRABLE INITIALLY DEFERRED" in sql
    assert "CREATE TRIGGER biomechanical_region_immutable" in sql
    assert "CREATE TRIGGER biomechanical_assessment_immutable" in sql
    assert "CREATE TRIGGER biomechanical_review_immutable" in sql
    migration.downgrade()
    assert "DROP FUNCTION guard_biomechanical_review()" in output.getvalue()


def test_optional_justifications_migration_preserves_data_and_result_constraints(monkeypatch):
    initial = load_migration("0013_biomechanical_assessments.py")
    migration = load_migration("0014_optional_assessment_justifications.py")
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE exercises (id UUID PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE biomechanical_scale_versions (version INTEGER PRIMARY KEY)"
            )
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(initial, "op", operations)
            monkeypatch.setattr(migration, "op", operations)
            initial.upgrade()
            connection.exec_driver_sql(
                "INSERT INTO exercise_region_demands VALUES "
                "('original', 'shoulder', 'assessed', 0, 'direct', 'Original justification')"
            )
            connection.exec_driver_sql(
                "INSERT INTO biomechanical_assessment_reviews "
                "(assessment_id, decision, notes) VALUES ('original', 'reviewed', 'Original notes')"
            )
            migration.upgrade()
            assert (
                connection.exec_driver_sql(
                    "SELECT justification FROM exercise_region_demands"
                ).scalar()
                == "Original justification"
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT notes FROM biomechanical_assessment_reviews"
                ).scalar()
                == "Original notes"
            )
            migration.downgrade()
            assert "ck_exercise_region_demand_reason" in {
                row["name"]
                for row in inspect(connection).get_check_constraints("exercise_region_demands")
            }
            migration.upgrade()
            connection.exec_driver_sql("UPDATE exercise_region_demands SET justification = ''")
            connection.exec_driver_sql("UPDATE biomechanical_assessment_reviews SET notes = ''")
            assert (
                connection.exec_driver_sql(
                    "SELECT justification FROM exercise_region_demands"
                ).scalar()
                == ""
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT notes FROM biomechanical_assessment_reviews"
                ).scalar()
                == ""
            )
            assert "ck_exercise_region_demand_result" in {
                row["name"]
                for row in inspect(connection).get_check_constraints("exercise_region_demands")
            }
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql("UPDATE exercise_region_demands SET demand_score = 6")
    finally:
        engine.dispose()


def test_optional_justifications_postgresql_migration_only_drops_text_constraints(monkeypatch):
    migration = load_migration("0014_optional_assessment_justifications.py")
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output, "literal_binds": True},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "DROP CONSTRAINT ck_exercise_region_demand_reason" in sql
    assert "DROP CONSTRAINT ck_biomechanical_review_notes" in sql
    assert sql.count("DROP CONSTRAINT") == 2
    assert "UPDATE " not in sql and "DROP TRIGGER" not in sql and "DROP TABLE" not in sql
