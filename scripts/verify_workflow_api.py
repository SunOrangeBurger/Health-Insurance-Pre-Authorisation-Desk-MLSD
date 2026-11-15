"""PostgreSQL-backed concurrency and hospital isolation acceptance."""
import asyncio
import json
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import httpx


async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as hospital, httpx.AsyncClient(base_url="http://localhost:8000") as reviewer, httpx.AsyncClient(base_url="http://localhost:8000") as other:
        async def login(client, email, password):
            response = await client.post('/v1/auth/login', headers={'X-Requested-With': 'desk'}, json={'email': email, 'password': password})
            response.raise_for_status()
            client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        await login(hospital, 'hospital@desk.local', os.environ['DESK_HOSPITAL_PASSWORD'])
        await login(other, 'hospital2@desk.local', os.environ['DESK_HOSPITAL_PASSWORD'])
        await login(reviewer, 'reviewer@desk.local', os.environ['DESK_REVIEWER_PASSWORD'])
        issued = (date.today() - timedelta(days=900)).isoformat()
        payload = {'request': {'request_id': str(uuid4()), 'policy_number': 'SYN-POL-0001',
            'policy_issue_date': issued, 'policy_start_date': issued, 'sum_insured': 500000,
            'patient_age': 44, 'patient_gender': 'F', 'admission_type': 'day_care',
            'planned_admission_date': (date.today()+timedelta(days=7)).isoformat(),
            'diagnosis_text': 'Synthetic cataract', 'procedure_text': 'Synthetic concurrency test',
            'procedure_code': 'SYN-001', 'room_category_requested': 'single', 'estimated_cost': 75000,
            'hospital_id': 'SYN-HOSP-002', 'prior_conditions': [], 'notes': ''}}
        response = await hospital.post('/v1/cases', json=payload)
        response.raise_for_status()
        case = response.json()
        assert case['hospital_id'] == 'SYN-HOSP-001'
        duplicate = await hospital.post('/v1/cases', json=payload)
        assert duplicate.json()['id'] == case['id']
        url = '/v1/cases/' + case['id']
        assert (await other.get(url)).status_code == 404
        assert (await other.get('/v1/runs/' + case['run_id'])).status_code == 404
        for _ in range(60):
            if (await reviewer.get(url)).json()['status'] == 'awaiting_review':
                break
            await asyncio.sleep(1)
        results = await asyncio.gather(*[
            reviewer.post(url+'/decision', json={'revision': 1, 'outcome': outcome,
                'reason': 'Synthetic concurrent human-review acceptance check.'})
            for outcome in ['approved', 'rejected']
        ])
        codes = sorted(r.status_code for r in results)
        assert codes == [200, 409], [r.text for r in results]
        assert (await hospital.get(url)).json()['status'] in {'approved', 'rejected'}
        result = {'passed': True, 'concurrent_decision_statuses': codes,
            'checks': ['Server-derived hospital identity', 'Duplicate submission idempotency',
                       'Cross-hospital case and run isolation', 'Exactly one concurrent reviewer decision succeeds'],
            'case_id': case['id']}
        Path('docs/evidence/workflow-api.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
