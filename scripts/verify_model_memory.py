"""Varied real cases reveal host prompt-cache growth hidden by identical prompts."""
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import httpx
import psutil


def main():
    client = httpx.Client(base_url='http://localhost:8000', timeout=10)
    response = client.post('/v1/auth/login', headers={'X-Requested-With': 'desk'}, json={
        'email': 'hospital@desk.local', 'password': os.environ['DESK_HOSPITAL_PASSWORD']})
    response.raise_for_status()
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    issue = (date.today()-timedelta(days=900)).isoformat()
    samples = []
    for i in range(10):
        payload = {'request_id': str(uuid4()), 'policy_number': 'SYN-POL-0001', 'policy_issue_date': issue,
            'policy_start_date': issue, 'sum_insured': 500000, 'patient_age': 44, 'patient_gender': 'F',
            'admission_type': 'day_care', 'planned_admission_date': (date.today()+timedelta(days=7)).isoformat(),
            'diagnosis_text': 'Synthetic cataract diagnosis', 'procedure_text': 'Phacoemulsification with IOL',
            'procedure_code': 'SYN-001', 'room_category_requested': 'single', 'estimated_cost': 75000,
            'hospital_id': 'SYN-HOSP-001', 'prior_conditions': [], 'notes': ''}
        response = client.post('/v1/cases', json={'request': payload})
        response.raise_for_status()
        case_id = response.json()['id']
        for _ in range(90):
            case = client.get('/v1/cases/'+case_id).json()
            if case['status'] != 'processing':
                break
            time.sleep(1)
        assert case['processing_status'] == 'completed', case
        rss = sum(p.info['memory_info'].rss for p in psutil.process_iter(['name', 'memory_info'])
                  if (p.info['name'] or '').lower().startswith('llama-server'))
        sample = {'case': i+1, 'case_id': case_id, 'runner_rss_bytes': rss,
                  'available_bytes': psutil.virtual_memory().available}
        samples.append(sample)
        print(json.dumps(sample), flush=True)
        if psutil.virtual_memory().available < max(2*1024**3, psutil.virtual_memory().total*.15):
            raise AssertionError('RAM reserve breached during memory probe')
    steady = [s['runner_rss_bytes'] for s in samples[3:]]
    result = {'passed': max(steady)/min(steady) <= 1.1, 'host_prompt_cache_mib': 0, 'samples': samples,
              'steady_rss_growth_fraction': max(steady)/min(steady)-1}
    Path('docs/evidence/model-memory-cache0.json').write_text(json.dumps(result, indent=2))
    assert result['passed'], result


if __name__ == '__main__':
    main()
