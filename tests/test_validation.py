from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from preauth.api.schemas import PreauthRequest


def valid_payload() -> dict:
    issue = date.today() - timedelta(days=400)
    return {
        "request_id": "TEST-0001",
        "policy_number": "SYN-POL-0001",
        "policy_issue_date": issue,
        "policy_start_date": issue,
        "sum_insured": 500_000,
        "patient_age": 34,
        "patient_gender": "F",
        "admission_type": "planned_surgical",
        "planned_admission_date": date.today() + timedelta(days=3),
        "diagnosis_text": "Synthetic diagnosis",
        "procedure_text": "Synthetic procedure",
        "procedure_code": "SYN-001",
        "room_category_requested": "single",
        "estimated_cost": 100_000,
        "hospital_id": "SYN-HOSP-001",
        "prior_conditions": [],
        "notes": "Synthetic test only",
    }


def test_valid_request() -> None:
    request = PreauthRequest.model_validate(valid_payload())
    assert request.policy_number == "SYN-POL-0001"
    assert request.validation_flags == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sum_insured", 99_000),
        ("patient_age", 101),
        ("patient_gender", "X"),
        ("admission_type", "outpatient"),
        ("estimated_cost", 0),
        ("hospital_id", "REAL-HOSPITAL"),
    ],
)
def test_invalid_field_constraints(field: str, value) -> None:
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        PreauthRequest.model_validate(payload)


def test_unknown_fields_are_rejected() -> None:
    payload = valid_payload()
    payload["patient_name"] = "Not allowed"
    with pytest.raises(ValidationError):
        PreauthRequest.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"policy_issue_date": date.today() + timedelta(days=1)},
        {
            "policy_issue_date": date.today() - timedelta(days=10),
            "policy_start_date": date.today() - timedelta(days=20),
        },
        {"planned_admission_date": date.today() - timedelta(days=2)},
        {"admission_type": "maternity", "patient_gender": "M"},
        {"admission_type": "maternity", "patient_age": 11},
    ],
)
def test_cross_field_violations(changes: dict) -> None:
    payload = valid_payload()
    payload.update(changes)
    with pytest.raises(ValidationError):
        PreauthRequest.model_validate(payload)


def test_high_estimate_is_flagged_not_rejected() -> None:
    payload = valid_payload()
    payload["sum_insured"] = 100_000
    payload["estimated_cost"] = 160_000
    request = PreauthRequest.model_validate(payload)
    assert request.validation_flags == ["estimated_cost_exceeds_150_percent_of_sum_insured"]
