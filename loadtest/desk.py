"""Authenticated real-model case workload. Credentials come from environment."""
import os
import time
from datetime import date, timedelta
from uuid import uuid4

import gevent
from locust import HttpUser, between, events, task
from gevent.lock import Semaphore

_login_lock = Semaphore()
_session = None


class HospitalUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Processing benchmark: share one seeded hospital session, keeping the
        # deliberately restrictive login limiter out of the capacity workload.
        global _session
        with _login_lock:
            if _session is None:
                response = self.client.post('/v1/auth/login', json={
                    'email': os.environ.get('DESK_LOAD_EMAIL', 'hospital@desk.local'),
                    'password': os.environ['DESK_HOSPITAL_PASSWORD'],
                }, headers={'X-Requested-With': 'desk'}, name='login')
                response.raise_for_status()
                _session = (response.json()['csrf_token'], self.client.cookies.get_dict())
        self.headers = {'X-CSRF-Token': _session[0]}
        self.client.cookies.update(_session[1])

    @task(3)
    def browse(self):
        self.client.get('/v1/cases', name='case list')

    @task
    def submit(self):
        start = time.perf_counter()
        issued = (date.today() - timedelta(days=900)).isoformat()
        payload = {'request_id': str(uuid4()), 'policy_number': 'SYN-POL-0001',
                   'policy_issue_date': issued, 'policy_start_date': issued,
                   'sum_insured': 500000, 'patient_age': 44, 'patient_gender': 'F',
                   'admission_type': 'day_care',
                   'planned_admission_date': (date.today() + timedelta(days=7)).isoformat(),
                   'diagnosis_text': 'Age-related cataract',
                   'procedure_text': 'Phacoemulsification with intraocular lens implantation',
                   'procedure_code': 'SYN-001', 'room_category_requested': 'single',
                   'estimated_cost': 75000, 'hospital_id': 'SYN-HOSP-001',
                   'prior_conditions': [], 'notes': ''}
        accepted = self.client.post('/v1/cases', json={'request': payload},
                                    headers=self.headers, name='case submission')
        if accepted.status_code != 202:
            return
        case_id = accepted.json()['id']
        error = RuntimeError('processing deadline exceeded')
        while time.perf_counter() - start < 120:
            gevent.sleep(1)
            response = self.client.get('/v1/cases/' + case_id, name='case poll')
            if response.status_code != 200:
                error = RuntimeError('poll failed')
                break
            case = response.json()
            if case['status'] != 'processing':
                error = None if case['processing_status'] in {'completed', 'escalated'} else RuntimeError('degraded or failed assessment')
                break
        events.request.fire(request_type='E2E', name='machine assessment',
                            response_time=(time.perf_counter() - start) * 1000,
                            response_length=0, exception=error, context={})
