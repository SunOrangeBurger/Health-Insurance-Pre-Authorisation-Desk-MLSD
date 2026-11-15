"""Real Ollama/PostgreSQL acceptance; creates synthetic cases and reusable decisions."""
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import httpx


def main():
    hospital = httpx.Client(base_url='http://localhost:8000', timeout=10)
    reviewer = httpx.Client(base_url='http://localhost:8000', timeout=10)
    for client, email, password in [(hospital, 'hospital@desk.local', os.environ['DESK_HOSPITAL_PASSWORD']),
                                    (reviewer, 'reviewer@desk.local', os.environ['DESK_REVIEWER_PASSWORD'])]:
        response = client.post('/v1/auth/login', headers={'X-Requested-With': 'desk'}, json={'email': email, 'password': password})
        response.raise_for_status()
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    amount = 70000 + int(time.time()) % 10000
    checks = []
    cases = []
    def submit(days=900, paraphrase=False, notes='', extra_cost=0):
        issued = (date.today()-timedelta(days=days)).isoformat()
        request = {'request_id': str(uuid4()), 'policy_number': 'SYN-POL-0001', 'policy_issue_date': issued,
            'policy_start_date': issued, 'sum_insured': 500000, 'patient_age': 44, 'patient_gender': 'F',
            'admission_type': 'day_care', 'planned_admission_date': (date.today()+timedelta(days=7)).isoformat(),
            'diagnosis_text': 'Synthetic cataract diagnosis',
            'procedure_text': 'Phacoemulsification with intraocular lens implantation' if paraphrase else 'Phacoemulsification with IOL',
            'procedure_code': 'SYN-001', 'room_category_requested': 'single', 'estimated_cost': amount+extra_cost,
            'hospital_id': 'SYN-HOSP-001', 'prior_conditions': [], 'notes': notes}
        response = hospital.post('/v1/cases', json={'request': request})
        response.raise_for_status()
        case_id = response.json()['id']
        started = time.perf_counter()
        while time.perf_counter()-started < 100:
            response = hospital.get('/v1/cases/'+case_id)
            response.raise_for_status()
            case = response.json()
            if case['status'] != 'processing':
                cases.append({'case_id': case_id, 'status': case['status'], 'decision': case['decision'],
                              'assessment': (case.get('recommendation') or {}).get('ai_assessment')})
                print(json.dumps(cases[-1]), flush=True)
                return case
            time.sleep(1)
        raise AssertionError('Case did not finish')
    def decide(case, outcome):
        response = reviewer.post('/v1/cases/'+case['id']+'/decision', json={'revision': case['revision'],
            'outcome': outcome, 'reusable': True, 'reason': 'Synthetic precedent acceptance: verified waiting-period policy basis.'})
        response.raise_for_status()
        rows = reviewer.get('/v1/precedents').json()['items']
        return next(p['id'] for p in rows if p['case_id'] == case['id'])
    source = submit()
    approval = decide(source, 'approved')
    automatic = submit(paraphrase=True)
    assert automatic['status'] == 'approved' and automatic['decision']['source'] == 'precedent'
    checks.append('Human approval enables semantic-paraphrase automatic approval')
    exception = submit(notes='Additional mitigating circumstances need human review')
    assert exception['status'] == 'awaiting_review'
    changed = submit(extra_cost=1000)
    assert changed['status'] == 'awaiting_review'
    checks.append('Mitigating notes and material cost changes force review')
    response = reviewer.post('/v1/precedents/'+approval+'/disable')
    response.raise_for_status()
    revoked = submit()
    assert revoked['status'] == 'awaiting_review'
    checks.append('Revoked precedent cannot decide future cases')
    source = submit(days=330)
    rejection = decide(source, 'rejected')
    automatic = submit(days=330, paraphrase=True)
    assert automatic['status'] == 'rejected' and automatic['decision']['source'] == 'precedent'
    checks.append('Human rejection enables semantic-paraphrase automatic rejection')
    response = reviewer.post('/v1/cases/'+automatic['id']+'/override', json={'revision': automatic['revision'],
        'outcome': 'approved', 'reusable': False, 'reason': 'Synthetic human override for a documented individual exception.'})
    response.raise_for_status()
    assert response.json()['decision']['source'] == 'human'
    rows = reviewer.get('/v1/precedents').json()['items']
    assert next(p for p in rows if p['id'] == rejection)['active'] is False
    checks.append('Human override preserves history and disables source precedent')
    Path('docs/evidence/precedent-flow.json').write_text(json.dumps({'passed': True, 'checks': checks, 'cases': cases}, indent=2))
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
