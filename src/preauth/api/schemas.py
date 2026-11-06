from datetime import date, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CONTRACT_VERSION = "1.0"


class AdmissionType(StrEnum):
    PLANNED_SURGICAL = "planned_surgical"
    DAY_CARE = "day_care"
    EMERGENCY = "emergency"
    MATERNITY = "maternity"


class PatientGender(StrEnum):
    M = "M"
    F = "F"
    O = "O"


class RoomCategory(StrEnum):
    GENERAL = "general"
    SHARED = "shared"
    SINGLE = "single"
    DELUXE = "deluxe"


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]


class PreauthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")
    policy_number: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{5,31}$")
    policy_issue_date: date
    policy_start_date: date
    sum_insured: int = Field(ge=100_000, le=10_000_000, multiple_of=1_000)
    patient_age: int = Field(ge=0, le=100)
    patient_gender: PatientGender
    admission_type: AdmissionType
    planned_admission_date: date
    diagnosis_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
    procedure_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    procedure_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9.-]{2,20}$")
    room_category_requested: RoomCategory
    estimated_cost: float = Field(gt=0, le=5_000_000)
    hospital_id: str = Field(pattern=r"^SYN-HOSP-[A-Z0-9-]{2,24}$")
    prior_conditions: list[ShortText] = Field(default_factory=list, max_length=20)
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @model_validator(mode="after")
    def validate_dates_and_maternity(self) -> "PreauthRequest":
        today = date.today()
        if self.policy_issue_date > today:
            raise ValueError("policy_issue_date must not be in the future")
        if self.policy_start_date < self.policy_issue_date:
            raise ValueError("policy_start_date must be on or after policy_issue_date")
        if self.planned_admission_date < self.policy_start_date:
            raise ValueError("planned_admission_date must be on or after policy_start_date")
        if self.admission_type == AdmissionType.EMERGENCY:
            if self.planned_admission_date < today - timedelta(days=1):
                raise ValueError("emergency admission may not be more than 24 hours in the past")
        elif self.planned_admission_date < today:
            raise ValueError("planned_admission_date must not be in the past")
        if self.admission_type == AdmissionType.MATERNITY:
            if self.patient_gender == PatientGender.M:
                raise ValueError("maternity admission is incompatible with patient_gender M")
            if self.patient_age < 12:
                raise ValueError("maternity admission requires patient_age of at least 12")
        return self

    @property
    def validation_flags(self) -> list[str]:
        if self.estimated_cost > self.sum_insured * 1.5:
            return ["estimated_cost_exceeds_150_percent_of_sum_insured"]
        return []


class ValidationErrorItem(BaseModel):
    field: str
    code: str
    message: str


class QuarantineResponse(BaseModel):
    quarantine_id: str
    contract_version: str
    errors: list[ValidationErrorItem]


class SubmissionResponse(BaseModel):
    run_id: str
    status: Literal["queued"]
    poll_url: str


class RunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "escalated", "failed", "degraded"]
    correlation_id: str
    result: dict[str, Any] | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    timings: dict[str, str | None] = Field(default_factory=dict)
    error: str | None = None


class QueueJobMessage(BaseModel):
    run_id: str
    correlation_id: str
    contract_version: str = CONTRACT_VERSION


class FeedbackRequest(BaseModel):
    satisfactory: bool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class LLMRequest(BaseModel):
    messages: list[dict[str, str]]
    temperature: float = Field(default=0, ge=0, le=2)


class LLMResponse(BaseModel):
    content: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
