import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from preauth.llm.assessment import assess


class Client:
    def __init__(self, content):
        self.content = content

    async def complete(self, request):
        assert request.output_schema
        return SimpleNamespace(content=self.content, prompt_tokens=50, completion_tokens=25)


@pytest.mark.asyncio
@pytest.mark.parametrize('fenced', [False, True])
async def test_verified_structured_assessment(fenced):
    body = json.dumps({'case_summary': 'A 44-year-old patient requests day-care cataract surgery.', 'recommendation': 'approve', 'rationale': 'The cited policy waiting period is served.',
                       'clause_ids': ['B.1.1'], 'exception_flags': []})
    if fenced:
        body = '```json\n' + body + '\n```'
    evidence = {'citations': [{'id': 'B.1.1'}], 'verification': {'passed': True}, 'coverage_position': 'waiting_period_served'}
    result = await assess(Client(body), {}, evidence)
    assert result['case_summary'] == 'A 44-year-old patient requests day-care cataract surgery.'
    assert result['prompt_version'] == 'claims-reviewer/v2'
    assert result['recommendation'] == 'approve'
    assert result['prompt_tokens'] == 50
    assert result['model_rationale'] == 'The cited policy waiting period is served.'
    assert result['rationale'] == 'Policy evidence requires a human review.'


@pytest.mark.asyncio
@pytest.mark.parametrize('clause,verified,position', [('invented', True, 'waiting_period_served'), ('B.1.1', False, 'waiting_period_served'), ('B.1.1', True, 'waiting_period_not_served')])
async def test_unsupported_conflicting_or_unverified_model_approval_requires_review(clause, verified, position):
    body = json.dumps({'case_summary': 'Synthetic cataract request for review.', 'recommendation': 'approve', 'rationale': 'A model recommendation requiring verification.', 'clause_ids': [clause], 'exception_flags': []})
    result = await assess(Client(body), {}, {'citations': [{'id': 'B.1.1'}], 'verification': {'passed': verified}, 'coverage_position': position})
    assert result['recommendation'] == 'needs_information'
    assert result['exception_flags']


@pytest.mark.asyncio
async def test_malformed_model_output_is_not_a_decision():
    with pytest.raises(ValidationError):
        await assess(Client('not valid JSON'), {}, {})


@pytest.mark.asyncio
async def test_generated_summary_currency_matches_inr_contract():
    body = json.dumps({'case_summary': 'Cataract surgery requested for $75,000 USD.',
                       'recommendation': 'approve', 'rationale': 'The waiting period is served.',
                       'clause_ids': ['B.1.1'], 'exception_flags': []})
    result = await assess(Client(body), {}, {'citations': [{'id': 'B.1.1'}], 'verification': {'passed': True}})
    assert '$' not in result['case_summary'] and 'USD' not in result['case_summary']
    assert 'INR' in result['case_summary']
