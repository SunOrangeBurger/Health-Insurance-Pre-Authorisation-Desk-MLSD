"""Authorize one synthetic nominal fixture for the soak; revoke it afterwards."""
import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import httpx

STATE = Path('docs/evidence/soak-precedent.json')


def login(email, password):
    client = httpx.Client(base_url='http://localhost:8000', timeout=10)
    response = client.post('/v1/auth/login', headers={'X-Requested-With': 'desk'}, json={'email': email, 'password': password})
    response.raise_for_status()
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    reviewer = login('reviewer@desk.local', os.environ['DESK_REVIEWER_PASSWORD'])
    if args.disable:
        state = json.loads(STATE.read_text())
        response = reviewer.post('/v1/precedents/'+state['precedent_id']+'/disable')
        response.raise_for_status()
        state['disabled_after_test'] = True
        STATE.write_text(json.dumps(state, indent=2))
        print('Synthetic soak precedent disabled')
        return
    hospital = login('hospital@desk.local', os.environ['DESK_HOSPITAL_PASSWORD'])
    issued = (date.today()-timedelta(days=900)).isoformat()
    payload = {'request_id': str(uuid4()), 'policy_number': 'SYN-POL-0001',
               'policy_issue_date': issued, 'policy_start_date': issued, 'sum_insured': 500000,
               'patient_age': 44, 'patient_gender': 'F', 'admission_type': 'day_care',
               'planned_admission_date': (date.today()+timedelta(days=7)).isoformat(),
               'diagnosis_text': 'Age-related cataract',
               'procedure_text': 'Phacoemulsification with intraocular lens implantation',
               'procedure_code': 'SYN-001', 'room_category_requested': 'single',
               'estimated_cost': 75000, 'hospital_id': 'SYN-HOSP-001', 'prior_conditions': [], 'notes': ''}
    response = hospital.post('/v1/cases', json={'request': payload})
    response.raise_for_status()
    case_id = response.json()['id']
    for _ in range(120):
        response = hospital.get('/v1/cases/'+case_id)
        response.raise_for_status()
        case = response.json()
        if case['status'] != 'processing':
            break
        time.sleep(1)
    else:
        raise AssertionError('Fixture assessment timed out')
    assert case['status'] == 'awaiting_review' and case['reusable_eligible'], 'Fixture is not eligible; do not bypass review gates'
    response = reviewer.post('/v1/cases/'+case_id+'/decision', json={
        'revision': case['revision'], 'outcome': 'approved', 'reusable': True,
        'reason': 'Synthetic load fixture: verified cataract coverage and waiting period served; authorize matching demonstration cases.'})
    response.raise_for_status()
    response = reviewer.get('/v1/precedents')
    response.raise_for_status()
    precedent = next(p for p in response.json()['items'] if p['case_id'] == case_id and p['active'])
    state = {'case_id': case_id, 'precedent_id': precedent['id'], 'disabled_after_test': False,
             'purpose': 'Synthetic five-minute stability test; no real claim or clinical decision.'}
    STATE.write_text(json.dumps(state, indent=2))
    print(json.dumps(state))


if __name__ == '__main__':
    main()
