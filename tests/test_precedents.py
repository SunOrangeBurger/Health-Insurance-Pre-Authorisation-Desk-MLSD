from types import SimpleNamespace
import pytest
from preauth.precedents import choose_precedent, eligible, material_facts
from tests.test_validation import valid_payload
from preauth.config import Settings


def test_automatic_decisions_are_opt_in_outside_demo_profile():
    assert Settings(_env_file=None).precedent_automation_enabled is False


def test_conflicting_revoked_and_materially_different_precedents():
    facts = {"cost": 100}
    a = SimpleNamespace(active=True, outcome="approved", facts=facts)
    b = SimpleNamespace(active=True, outcome="rejected", facts=facts)
    assert choose_precedent(facts, [a, b], [.99, .99], .9) is None
    b.active = False
    assert choose_precedent(facts, [a, b], [.99, .99], .9) is a
    assert choose_precedent({"cost": 101}, [a], [1.0], .9) is None
    assert choose_precedent(facts, [a], [.8], .9) is None


def test_exceptions_require_review_even_with_verified_evidence():
    request = valid_payload()
    request["notes"] = ""
    evidence = {"verification": {"passed": True}, "citations": [{"id": "A"}],
                "coverage_position": "waiting_period_served",
                "ai_assessment": {"recommendation": "approve", "exception_flags": []}}
    assert eligible(request, evidence)
    request['notes'] = None
    assert eligible(request, evidence)
    request["notes"] = "An exceptional circumstance"
    assert not eligible(request, evidence)
    request["notes"] = ""
    evidence["ai_assessment"]["exception_flags"] = ["uncertain waiting period"]
    assert not eligible(request, evidence)


@pytest.mark.parametrize('field,value', [('prior_conditions', ['diabetes']), ('room_category_requested', 'deluxe'), ('admission_type', 'emergency'), ('notes', 'An accident exception needs review')])
def test_mandatory_exception_gates_do_not_depend_on_model_flags(field, value):
    request = valid_payload()
    request['notes'] = ''
    request[field] = value
    evidence = {'verification': {'passed': True}, 'citations': [{'id': 'A'}],
                'coverage_position': 'waiting_period_served',
                'ai_assessment': {'recommendation': 'approve', 'exception_flags': []}}
    assert not eligible(request, evidence)
