import pytest
from preauth.store.models import Run
from tests.test_auth import client, login
from tests.test_validation import valid_payload


@pytest.mark.asyncio
async def test_submit_review_clarify_and_resubmit(client):
    csrf = await login(client)
    payload = valid_payload()
    for key, value in payload.items():
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    body = {"request": payload}
    response = await client.http.post("/v1/cases", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 202, response.text
    case = response.json()
    duplicate = await client.http.post("/v1/cases", json=body, headers={"X-CSRF-Token": csrf})
    assert duplicate.json()["id"] == case["id"]
    assert case["hospital_id"] == "A"  # ignores forged/submitted hospital identity
    async with client.sessions() as session:
        run = await session.get(Run, case["run_id"])
        run.status = "completed"
        run.result = {"route": "medical-review"}
        await session.commit()
    await login(client, "b")
    assert (await client.http.get("/v1/cases/" + case["id"])).status_code == 404
    assert (await client.http.get("/v1/cases")).json()["items"] == []
    csrf = await login(client, "r")
    decision = {"revision": 1, "outcome": "information_requested", "reason": "Please clarify the diagnosis."}
    url = "/v1/cases/" + case["id"]
    response = await client.http.post(url + "/decision", json=decision, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    assert (await client.http.post(url + "/decision", json=decision, headers={"X-CSRF-Token": csrf})).status_code == 409
    csrf = await login(client)
    response = await client.http.post(url + "/resubmit?revision=1", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 202, response.text
    assert response.json()["revision"] == 2
    assert response.json()["run_id"] != case["run_id"]
    assert len((await client.http.get(url)).json()["history"]) == 3
    assert (await client.http.post(url + "/resubmit?revision=1", json=body, headers={"X-CSRF-Token": csrf})).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["approved", "rejected"])
async def test_final_decision_role_and_filters(client, outcome):
    csrf = await login(client)
    payload = valid_payload()
    payload = {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in payload.items()}
    response = await client.http.post('/v1/cases', json={'request': payload}, headers={'X-CSRF-Token': csrf})
    case = response.json()
    url = '/v1/cases/' + case['id']
    decision = {'revision': 1, 'outcome': outcome, 'reason': 'Reviewed the supplied policy evidence.'}
    assert (await client.http.post(url + '/decision', json=decision, headers={'X-CSRF-Token': csrf})).status_code == 403
    async with client.sessions() as session:
        run = await session.get(Run, case['run_id'])
        run.status = 'completed'
        await session.commit()
    csrf = await login(client, 'r')
    assert len((await client.http.get('/v1/cases?status=awaiting_review')).json()['items']) == 1
    assert (await client.http.post(url + '/decision', json=decision, headers={'X-CSRF-Token': csrf})).status_code == 200
    assert (await client.http.get('/v1/cases?status=awaiting_review')).json()['items'] == []
    assert len((await client.http.get('/v1/cases?status=' + outcome)).json()['items']) == 1
    csrf = await login(client)
    assert (await client.http.get(url)).json()['decision']['outcome'] == outcome
    assert (await client.http.post(url + '/resubmit?revision=1', json={'request': payload}, headers={'X-CSRF-Token': csrf})).status_code == 409
