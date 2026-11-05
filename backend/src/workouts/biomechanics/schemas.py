from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
OptionalJustification = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
RegionCode = Literal["shoulder", "lumbar_spine", "cervical_spine", "knee", "elbow"]
RoleCode = Literal["direct", "secondary", "stabilizing"]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegionDefinition(StrictSchema):
    code: RegionCode
    label: ShortText
    description: Description


class RoleDefinition(StrictSchema):
    code: RoleCode
    label: ShortText
    description: Description


class ScoreDefinition(StrictSchema):
    score: Annotated[StrictInt, Field(ge=0, le=5)]
    label: ShortText
    description: Description


class ScaleDefinition(StrictSchema):
    title: ShortText
    disclaimer: Description
    reference_conditions: Description
    evaluation_criteria: Description
    consistency_rules: Description
    unassessed_guidance: Description
    regions: list[RegionDefinition] = Field(min_length=5, max_length=5)
    roles: list[RoleDefinition] = Field(min_length=3, max_length=3)
    scores: list[ScoreDefinition] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def unique_entries(self) -> Self:
        if len({region.code for region in self.regions}) != 5:
            raise ValueError("Informe cada uma das cinco regiões exatamente uma vez.")
        if len({role.code for role in self.roles}) != 3:
            raise ValueError("Informe cada um dos três tipos de participação exatamente uma vez.")
        if {score.score for score in self.scores} != set(range(6)):
            raise ValueError("Informe cada nota de 0 a 5 exatamente uma vez.")
        return self


class ScaleCreate(StrictSchema):
    base_version: Annotated[StrictInt, Field(ge=1)]
    change_reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]
    definition: ScaleDefinition


class ScaleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    change_reason: str
    created_by: UUID | None
    created_at: datetime


class ScaleVersion(ScaleSummary):
    definition: ScaleDefinition


class ScaleHistory(BaseModel):
    items: list[ScaleSummary]
    page: int
    total: int


ReviewDecision = Literal["reviewed", "rejected"]
ReviewStatus = Literal["pending", "reviewed", "rejected"]


class RegionDemandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_code: RegionCode
    assessment_status: Literal["assessed", "unassessed"]
    demand_score: int | None
    demand_role: RoleCode | None
    justification: str


class AssessmentReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: ReviewDecision
    notes: str
    reviewed_by: UUID | None
    reviewed_at: datetime


class AssessmentSummary(BaseModel):
    id: UUID
    exercise_id: UUID
    exercise_name: str
    images: list[str]
    scale_version: int
    uses_current_scale: bool
    assessment_method: Literal["manual", "ai", "rule"]
    assessment_source: str
    review_status: ReviewStatus
    created_at: datetime


class RegionScorePreview(BaseModel):
    region_code: RegionCode
    label: str
    assessment_status: Literal["assessed", "unassessed"] | None
    demand_score: int | None


class AssessmentListItem(AssessmentSummary):
    region_scores: list[RegionScorePreview]


class AssessmentCounts(BaseModel):
    total_exercises: int
    validated_exercises: int
    unvalidated_exercises: int


class AssessmentFilters(BaseModel):
    muscle_groups: list[str]
    categories: list[str]


class AssessmentList(BaseModel):
    items: list[AssessmentListItem]
    counts: AssessmentCounts
    filters: AssessmentFilters
    page: int
    page_size: int
    total: int
    total_pages: int


class AssessmentDetail(AssessmentSummary):
    content_hash: str
    supersedes_id: UUID | None
    execution_context: str
    created_by: UUID | None
    regions: list[RegionDemandOut]
    review: AssessmentReviewOut | None
    scale: ScaleVersion
    validation_errors: list[str]


class AssessmentReviewIn(StrictSchema):
    decision: ReviewDecision
    notes: OptionalJustification = ""
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class RegionDemandIn(StrictSchema):
    region_code: RegionCode
    assessment_status: Literal["assessed", "unassessed"]
    demand_score: Annotated[StrictInt, Field(ge=0, le=5)] | None
    demand_role: RoleCode | None
    justification: OptionalJustification = ""

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.assessment_status == "assessed":
            if self.demand_score is None or self.demand_role is None:
                raise ValueError("Região avaliada exige nota e participação.")
        elif self.demand_score is not None or self.demand_role is not None:
            raise ValueError("Região não avaliada não pode ter nota ou participação.")
        return self


class AssessmentCorrectionIn(StrictSchema):
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)] = ""
    regions: list[RegionDemandIn] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def unique_regions(self) -> Self:
        if len({region.region_code for region in self.regions}) != 5:
            raise ValueError("Informe cada uma das cinco regiões exatamente uma vez.")
        return self
