import pytest
from preauth.store.models import Case, Precedent, Run
from tests.test_auth import client, login


@pytest.mark.asyncio
async def test_reviewer_can_disable_and_override_but_hospital_cannot(client):
    async with client.sessions() as session:
        session.add(Run(id='auto-run', status='completed', correlation_id='control-test', request_payload={}))
        session.add(Precedent(id='p', case_id='source', revision=1, policy_version='v1', outcome='approved', reason='Human reason', facts={}, description='Synthetic source', active=True))
        session.add(Case(id='auto-case', hospital_id='A', run_id='auto-run', revision=1, status='approved', policy_version='v1', decision={'source': 'precedent', 'precedent_id': 'p', 'outcome': 'approved'}))
        await session.commit()
    csrf = await login(client)
    assert (await client.http.get('/v1/precedents')).status_code == 403
    assert (await client.http.post('/v1/precedents/p/disable', headers={'X-CSRF-Token': csrf})).status_code == 403
    csrf = await login(client, 'r')
    payload = {'revision': 1, 'outcome': 'rejected', 'reason': 'A mitigating circumstance needs a different decision.'}
    response = await client.http.post('/v1/cases/auto-case/override', json=payload, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200, response.text
    assert response.json()['decision']['source'] == 'human'
    assert response.json()['decision']['overrides']['source'] == 'precedent'
    assert (await client.http.get('/v1/precedents')).json()['items'][0]['active'] is False
    assert (await client.http.post('/v1/cases/auto-case/override', json=payload, headers={'X-CSRF-Token': csrf})).status_code == 409
