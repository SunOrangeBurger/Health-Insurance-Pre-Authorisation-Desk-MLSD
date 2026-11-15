import json
from datetime import date
from types import SimpleNamespace
import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from preauth.automation import apply_precedent
from preauth.precedents import material_facts
from preauth.store.migrations import migrate
from preauth.store.models import Case, CaseEvent, Precedent, Run
from tests.test_validation import valid_payload


class Embedder:
    name = 'fixture'
    def encode(self, texts):
        return np.array([[1., 0.] for _ in texts])


@pytest_asyncio.fixture
async def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'evals').mkdir()
    (tmp_path / 'evals/precedent_calibration.json').write_text(json.dumps({'passed': True, 'embedding_model': 'fixture', 'threshold': .72}))
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await migrate(connection)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    request = valid_payload()
    request = {k: v.isoformat() if isinstance(v, date) else v for k, v in request.items()}
    request['notes'] = ''
    evidence = {'verification': {'passed': True}, 'citations': [{'id': 'B.1.1', 'text': 'policy evidence'}],
                'coverage_position': 'waiting_period_served',
                'ai_assessment': {'recommendation': 'approve', 'exception_flags': [], 'rationale': 'Verified policy evidence.'}}
    async with sessions() as session:
        session.add(Run(id='run', status='completed', correlation_id='test', request_payload=request))
        session.add(Case(id='case', hospital_id='hospital', run_id='run', revision=1, status='processing', policy_version='policy-v1'))
        await session.commit()
    yield SimpleNamespace(sessions=sessions, request=request, evidence=evidence, path=tmp_path)
    await engine.dispose()


async def precedent(session, setup, id='p', outcome='approved', active=True, version='policy-v1'):
    session.add(Precedent(id=id, case_id='human-case', revision=1, policy_version=version,
        outcome=outcome, reason='Human reviewed policy evidence.', facts=material_facts(setup.request, setup.evidence),
        description='A differently worded clinical description.', active=active))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome,recommendation', [('approved', 'approve'), ('rejected', 'reject')])
async def test_human_precedent_automates_both_outcomes_once(setup, outcome, recommendation):
    setup.evidence['ai_assessment']['recommendation'] = recommendation
    async with setup.sessions() as session:
        await precedent(session, setup, outcome=outcome)
        await apply_precedent(session, 'run', setup.request, setup.evidence, Embedder())
        case = await session.get(Case, 'case')
        assert case.status == outcome and case.decision['source'] == 'precedent'
        await apply_precedent(session, 'run', setup.request, setup.evidence, Embedder())
        events = (await session.scalars(select(CaseEvent))).all()
        assert len(events) == 1
        assert len((await session.scalars(select(Precedent))).all()) == 1  # no recursive learning


@pytest.mark.asyncio
@pytest.mark.parametrize('condition', ['revoked', 'conflict', 'policy_changed', 'exception', 'facts_changed', 'evidence_changed', 'model_disagrees', 'calibration_missing', 'model_changed'])
async def test_exceptions_and_invalidated_precedents_require_human(setup, condition):
    async with setup.sessions() as session:
        await precedent(session, setup, active=condition != 'revoked', version='old-policy' if condition == 'policy_changed' else 'policy-v1')
        if condition == 'conflict':
            await precedent(session, setup, id='opposite', outcome='rejected')
        if condition == 'exception':
            setup.request['notes'] = 'Additional mitigating circumstances'
        if condition == 'facts_changed':
            setup.request['estimated_cost'] += 1000
        if condition == 'evidence_changed':
            setup.evidence['citations'][0]['text'] = 'Changed policy wording'
        if condition == 'model_disagrees':
            setup.evidence['ai_assessment']['recommendation'] = 'reject'
        if condition == 'calibration_missing':
            (setup.path/'evals/precedent_calibration.json').unlink()
        embedder = Embedder()
        if condition == 'model_changed':
            embedder.name = 'different-embedding-model'
        await apply_precedent(session, 'run', setup.request, setup.evidence, embedder)
        assert (await session.get(Case, 'case')).status == 'processing'
        assert not (await session.scalars(select(CaseEvent))).all()


@pytest.mark.asyncio
async def test_automatic_decision_rolls_back_with_uncommitted_run(setup):
    async with setup.sessions() as session:
        await precedent(session, setup)
        await apply_precedent(session, 'run', setup.request, setup.evidence, Embedder())
        await session.rollback()
    async with setup.sessions() as session:
        assert (await session.get(Case, 'case')).status == 'processing'
        assert not (await session.scalars(select(CaseEvent))).all()
