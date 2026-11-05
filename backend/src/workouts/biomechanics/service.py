import hashlib
import json
from datetime import timedelta
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from src.auth.models import utcnow
from src.workouts.biomechanics.models import (
    BiomechanicalAssessmentReview,
    BiomechanicalScaleVersion,
    ExerciseBiomechanicalAssessment,
    ExerciseRegionDemand,
)
from src.workouts.biomechanics.schemas import (
    AssessmentCorrectionIn,
    AssessmentCounts,
    AssessmentDetail,
    AssessmentFilters,
    AssessmentList,
    AssessmentListItem,
    AssessmentReviewIn,
    AssessmentReviewOut,
    AssessmentSummary,
    RegionDemandOut,
    RegionScorePreview,
    ReviewStatus,
    ScaleCreate,
    ScaleDefinition,
    ScaleHistory,
    ScaleSummary,
    ScaleVersion,
)
from src.workouts.exercises.models import Exercise, ExerciseTranslation


class ScaleUnavailableError(RuntimeError):
    pass


class ScaleConflictError(RuntimeError):
    pass


class UnchangedScaleError(ValueError):
    pass


def current_version(session: Session) -> BiomechanicalScaleVersion:
    scale = session.scalar(
        select(BiomechanicalScaleVersion)
        .order_by(BiomechanicalScaleVersion.version.desc())
        .limit(1)
    )
    if scale is None:
        raise ScaleUnavailableError("Escala não inicializada. Aplique as migrações do banco.")
    return scale


def list_versions(session: Session, page: int, page_size: int) -> ScaleHistory:
    items = session.scalars(
        select(BiomechanicalScaleVersion)
        .order_by(BiomechanicalScaleVersion.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ScaleHistory(
        items=[ScaleSummary.model_validate(item) for item in items],
        page=page,
        total=session.scalar(select(func.count()).select_from(BiomechanicalScaleVersion)) or 0,
    )


def create_version(session: Session, body: ScaleCreate, user_id: UUID) -> BiomechanicalScaleVersion:
    conflict = "Os critérios foram alterados por outro administrador. Recarregue a versão atual."
    current = current_version(session)
    if current.version != body.base_version:
        raise ScaleConflictError(conflict)
    definition = body.definition.model_dump(mode="json")
    if current.definition == definition:
        raise UnchangedScaleError("Altere os critérios antes de salvar uma nova versão.")
    scale = BiomechanicalScaleVersion(
        version=body.base_version + 1,
        definition=definition,
        change_reason=body.change_reason,
        created_by=user_id,
    )
    session.add(scale)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(BiomechanicalScaleVersion, body.base_version + 1) is not None:
            raise ScaleConflictError(conflict) from None
        raise
    session.refresh(scale)
    return scale


class AssessmentNotFoundError(LookupError):
    pass


class InvalidAssessmentError(ValueError):
    pass


def _catalog_query():
    localized = aliased(ExerciseTranslation)
    english = aliased(ExerciseTranslation)
    name = func.coalesce(localized.name, english.name, Exercise.name)
    statement = (
        select(ExerciseBiomechanicalAssessment, name.label("exercise_name"), Exercise.images)
        .join(Exercise, Exercise.id == ExerciseBiomechanicalAssessment.exercise_id)
        .outerjoin(
            localized,
            (localized.exercise_id == Exercise.id) & (localized.locale == "pt-BR"),
        )
        .outerjoin(
            english,
            (english.exercise_id == Exercise.id) & (english.locale == "en"),
        )
        .where(Exercise.owner_user_id.is_(None))
    )
    return statement, name


def _summary(
    assessment: ExerciseBiomechanicalAssessment,
    name: str,
    current_scale: int | None,
    images: list[str] | None,
) -> AssessmentSummary:
    return AssessmentSummary(
        id=assessment.id,
        exercise_id=assessment.exercise_id,
        exercise_name=name,
        images=images or [],
        scale_version=assessment.scale_version,
        uses_current_scale=assessment.scale_version == current_scale,
        assessment_method=assessment.assessment_method,
        assessment_source=assessment.assessment_source,
        review_status=assessment.review.decision if assessment.review else "pending",
        created_at=assessment.created_at,
    )


def list_assessments(
    session: Session,
    page: int,
    page_size: int,
    q: str | None,
    review_status: ReviewStatus | None,
    exercise_id: UUID | None,
    category: str | None = None,
    muscle_group: str | None = None,
) -> AssessmentList:
    statement, name = _catalog_query()
    if category is not None:
        statement = statement.where(Exercise.category == category)
    if muscle_group is not None:
        statement = statement.where(Exercise.muscle_group == muscle_group)
    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                name.ilike(pattern, escape="\\"),
                Exercise.name.ilike(pattern, escape="\\"),
                Exercise.source_id.ilike(pattern, escape="\\"),
            )
        )
    if exercise_id is not None:
        statement = statement.where(ExerciseBiomechanicalAssessment.exercise_id == exercise_id)
    if review_status == "pending":
        statement = statement.where(~ExerciseBiomechanicalAssessment.review.has())
    elif review_status is not None:
        statement = statement.where(
            ExerciseBiomechanicalAssessment.review.has(
                BiomechanicalAssessmentReview.decision == review_status
            )
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(
        statement.order_by(
            ExerciseBiomechanicalAssessment.created_at.desc(),
            ExerciseBiomechanicalAssessment.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    current_scale = session.scalar(select(func.max(BiomechanicalScaleVersion.version)))
    versions = {assessment.scale_version for assessment, _, _ in rows}
    definitions = {
        scale.version: ScaleDefinition.model_validate(scale.definition)
        for scale in session.scalars(
            select(BiomechanicalScaleVersion).where(BiomechanicalScaleVersion.version.in_(versions))
        )
    }
    items = []
    for assessment, exercise_name, images in rows:
        definition = definitions.get(assessment.scale_version)
        if definition is None:
            raise ScaleUnavailableError("Versão dos critérios da avaliação não encontrada.")
        results = {region.region_code: region for region in assessment.regions}
        previews = []
        for region in definition.regions:
            result = results.get(region.code)
            previews.append(
                RegionScorePreview(
                    region_code=region.code,
                    label=region.label,
                    assessment_status=result.assessment_status if result else None,
                    demand_score=result.demand_score if result else None,
                )
            )
        items.append(
            AssessmentListItem(
                **_summary(assessment, exercise_name, current_scale, images).model_dump(),
                region_scores=previews,
            )
        )
    return AssessmentList(
        items=items,
        counts=_assessment_counts(session),
        filters=AssessmentFilters(
            **{
                key: list(
                    session.scalars(
                        select(column)
                        .where(
                            Exercise.owner_user_id.is_(None),
                            column.is_not(None),
                            column != "",
                        )
                        .distinct()
                        .order_by(column)
                    ).all()
                )
                for key, column in (
                    ("muscle_groups", Exercise.muscle_group),
                    ("categories", Exercise.category),
                )
            }
        ),
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


def _assessment_counts(session: Session) -> AssessmentCounts:
    ranked = select(
        ExerciseBiomechanicalAssessment.id.label("id"),
        ExerciseBiomechanicalAssessment.exercise_id.label("exercise_id"),
        func.row_number()
        .over(
            partition_by=ExerciseBiomechanicalAssessment.exercise_id,
            order_by=(
                ExerciseBiomechanicalAssessment.created_at.desc(),
                ExerciseBiomechanicalAssessment.id.desc(),
            ),
        )
        .label("position"),
    ).subquery()
    total, validated = session.execute(
        select(
            func.count(Exercise.id),
            func.coalesce(
                func.sum(case((BiomechanicalAssessmentReview.decision == "reviewed", 1), else_=0)),
                0,
            ),
        )
        .select_from(Exercise)
        .outerjoin(ranked, (ranked.c.exercise_id == Exercise.id) & (ranked.c.position == 1))
        .outerjoin(
            BiomechanicalAssessmentReview,
            BiomechanicalAssessmentReview.assessment_id == ranked.c.id,
        )
        .where(Exercise.owner_user_id.is_(None))
    ).one()
    return AssessmentCounts(
        total_exercises=total,
        validated_exercises=validated,
        unvalidated_exercises=total - validated,
    )


def _validation_errors(
    assessment: ExerciseBiomechanicalAssessment,
    definition: ScaleDefinition,
) -> list[str]:
    expected = {region.code for region in definition.regions}
    actual = {region.region_code for region in assessment.regions}
    errors = []
    if actual != expected or len(assessment.regions) != len(expected):
        errors.append("A avaliação deve conter exatamente as cinco regiões da escala.")
    for region in assessment.regions:
        if region.assessment_status == "assessed":
            if (
                region.demand_score is None
                or not 0 <= region.demand_score <= 5
                or region.demand_role not in {role.code for role in definition.roles}
            ):
                errors.append(f"Nota ou participação inválida para {region.region_code}.")
        elif (
            region.assessment_status != "unassessed"
            or region.demand_score is not None
            or region.demand_role is not None
        ):
            errors.append(
                f"Região não avaliada deve ter nota e participação ausentes: {region.region_code}."
            )
    return errors


def assessment_detail(session: Session, assessment_id: UUID) -> AssessmentDetail:
    statement, _ = _catalog_query()
    row = session.execute(
        statement.where(ExerciseBiomechanicalAssessment.id == assessment_id).execution_options(
            populate_existing=True
        )
    ).one_or_none()
    if row is None:
        raise AssessmentNotFoundError("Avaliação não encontrada no catálogo global.")
    assessment, name, images = row
    scale = session.get(BiomechanicalScaleVersion, assessment.scale_version)
    if scale is None:
        raise ScaleUnavailableError("Versão dos critérios da avaliação não encontrada.")
    definition = ScaleDefinition.model_validate(scale.definition)
    summary = _summary(
        assessment,
        name,
        session.scalar(select(func.max(BiomechanicalScaleVersion.version))),
        images,
    )
    regions = [RegionDemandOut.model_validate(region) for region in assessment.regions]
    content = {
        "id": str(assessment.id),
        "exercise_id": str(assessment.exercise_id),
        "scale_version": assessment.scale_version,
        "definition": definition.model_dump(mode="json"),
        "execution_context": assessment.execution_context,
        "assessment_method": assessment.assessment_method,
        "assessment_source": assessment.assessment_source,
        "supersedes_id": str(assessment.supersedes_id) if assessment.supersedes_id else None,
        "regions": [region.model_dump(mode="json") for region in regions],
    }
    content_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return AssessmentDetail(
        **summary.model_dump(),
        content_hash=content_hash,
        supersedes_id=assessment.supersedes_id,
        execution_context=assessment.execution_context,
        created_by=assessment.created_by,
        regions=regions,
        review=AssessmentReviewOut.model_validate(assessment.review) if assessment.review else None,
        scale=ScaleVersion.model_validate(scale),
        validation_errors=_validation_errors(assessment, definition),
    )


def review_assessment(
    session: Session,
    assessment_id: UUID,
    body: AssessmentReviewIn,
    reviewer_id: UUID,
) -> AssessmentDetail:
    # Serialize review decisions with imports that lock this assessment in PostgreSQL.
    assessment = session.scalar(
        select(ExerciseBiomechanicalAssessment)
        .join(Exercise, Exercise.id == ExerciseBiomechanicalAssessment.exercise_id)
        .where(
            ExerciseBiomechanicalAssessment.id == assessment_id,
            Exercise.owner_user_id.is_(None),
        )
        .with_for_update(of=ExerciseBiomechanicalAssessment)
        .execution_options(populate_existing=True)
    )
    if assessment is None:
        raise AssessmentNotFoundError("Avaliação não encontrada no catálogo global.")
    if assessment.review is not None:
        raise ScaleConflictError(
            "Esta avaliação já foi revisada. Recarregue para consultar a decisão."
        )
    session.scalars(
        select(ExerciseRegionDemand)
        .where(ExerciseRegionDemand.assessment_id == assessment_id)
        .with_for_update()
    ).all()
    detail = assessment_detail(session, assessment_id)
    if detail.content_hash != body.content_hash:
        raise ScaleConflictError(
            "O conteúdo da avaliação mudou desde a consulta. Recarregue antes de revisar."
        )
    if body.decision == "reviewed" and detail.validation_errors:
        raise InvalidAssessmentError(" ".join(detail.validation_errors))
    review = BiomechanicalAssessmentReview(
        assessment_id=assessment_id,
        decision=body.decision,
        notes=body.notes,
        reviewed_by=reviewer_id,
    )
    session.add(review)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(BiomechanicalAssessmentReview, assessment_id) is not None:
            raise ScaleConflictError(
                "Esta avaliação já foi revisada. Recarregue para consultar a decisão."
            ) from None
        raise
    return assessment_detail(session, assessment_id)


def correct_assessment(
    session: Session,
    assessment_id: UUID,
    body: AssessmentCorrectionIn,
    author_id: UUID,
) -> AssessmentDetail:
    exercise_id = session.scalar(
        select(ExerciseBiomechanicalAssessment.exercise_id).where(
            ExerciseBiomechanicalAssessment.id == assessment_id
        )
    )
    exercise = session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id, Exercise.owner_user_id.is_(None))
        .with_for_update(of=Exercise)
    )
    if exercise is None:
        raise AssessmentNotFoundError("Avaliação não encontrada no catálogo global.")
    source = session.scalar(
        select(ExerciseBiomechanicalAssessment)
        .where(ExerciseBiomechanicalAssessment.id == assessment_id)
        .with_for_update(of=ExerciseBiomechanicalAssessment)
        .execution_options(populate_existing=True)
    )
    if source is None:
        raise AssessmentNotFoundError("Avaliação não encontrada no catálogo global.")
    session.scalars(
        select(ExerciseRegionDemand)
        .where(ExerciseRegionDemand.assessment_id == assessment_id)
        .with_for_update()
    ).all()
    detail = assessment_detail(session, assessment_id)
    if detail.content_hash != body.content_hash:
        raise ScaleConflictError(
            "A avaliação mudou desde a consulta. Recarregue antes de alterar as notas."
        )
    latest = session.scalar(
        select(ExerciseBiomechanicalAssessment)
        .where(ExerciseBiomechanicalAssessment.exercise_id == exercise.id)
        .order_by(
            ExerciseBiomechanicalAssessment.created_at.desc(),
            ExerciseBiomechanicalAssessment.id.desc(),
        )
        .limit(1)
    )
    if latest is None or latest.id != assessment_id:
        raise ScaleConflictError(
            "Já existe uma avaliação mais recente para este exercício. "
            "Consulte-a antes de corrigir."
        )
    previous = {region.region_code: region.model_dump() for region in detail.regions}
    changed = {region.region_code: region.model_dump() for region in body.regions}
    if previous == changed:
        raise InvalidAssessmentError("Altere ao menos uma nota, participação ou justificativa.")
    now = utcnow()
    # SQLite retorna datas sem fuso; PostgreSQL mantém timezone.
    source_time = source.created_at
    if source_time.tzinfo is None:
        source_time = source_time.replace(tzinfo=now.tzinfo)
    corrected = ExerciseBiomechanicalAssessment(
        exercise_id=source.exercise_id,
        scale_version=source.scale_version,
        supersedes_id=source.id,
        assessment_method="manual",
        assessment_source=(
            f"Correção administrativa: {body.reason}" if body.reason else "Correção administrativa"
        ),
        execution_context=source.execution_context,
        created_by=author_id,
        created_at=max(now, source_time + timedelta(microseconds=1)),
        regions=[ExerciseRegionDemand(**region.model_dump()) for region in body.regions],
    )
    definition = detail.scale.definition
    errors = _validation_errors(corrected, definition)
    if errors:
        raise InvalidAssessmentError(" ".join(errors))
    session.add(corrected)
    if source.review is None:
        session.add(
            BiomechanicalAssessmentReview(
                assessment_id=source.id,
                decision="rejected",
                notes="Rejeitada automaticamente por substituição por uma avaliação corrigida.",
                reviewed_by=author_id,
            )
        )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ScaleConflictError(
            "Não foi possível salvar a nova avaliação. Recarregue e tente novamente."
        ) from None
    return assessment_detail(session, corrected.id)
