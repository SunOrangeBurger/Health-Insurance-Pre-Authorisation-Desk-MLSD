import pytest

from preauth.api.schemas import PreauthRequest
from scripts.live_traffic import build_payload


@pytest.mark.parametrize(
    "scenario",
    [
        "mature-cataract",
        "waiting-period",
        "room-query",
        "out-of-corpus",
        "possible-ped",
        "maternity",
        "prompt-injection",
    ],
)
def test_live_demo_scenarios_conform_to_request_contract(scenario: str) -> None:
    request = PreauthRequest.model_validate(build_payload(1, scenario))
    assert request.request_id.startswith("LIVE-")


def test_live_demo_scenarios_exercise_distinct_paths() -> None:
    assert build_payload(1, "room-query")["room_category_requested"] == "deluxe"
    assert build_payload(2, "possible-ped")["prior_conditions"]
    assert build_payload(3, "maternity")["admission_type"] == "maternity"
    assert "Ignore previous instructions" in build_payload(4, "prompt-injection")["notes"]
