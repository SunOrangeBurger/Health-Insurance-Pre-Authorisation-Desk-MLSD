from datetime import date, timedelta
import time
from uuid import uuid4

from locust import HttpUser, between, events, task


TERMINAL = {"completed", "escalated", "degraded", "failed"}


class PreauthUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self) -> None:
        self.client_id = f"load-{uuid4()}"
        self.sequence = 0

    def payload(self) -> dict:
        self.sequence += 1
        admission = date.today() + timedelta(days=7)
        start = admission - timedelta(days=900)
        return {
            "request_id": f"LOAD-{uuid4().hex[:12].upper()}",
            "policy_number": f"SYN-{uuid4().hex[:12].upper()}",
            "policy_issue_date": start.isoformat(),
            "policy_start_date": start.isoformat(),
            "sum_insured": 500000,
            "patient_age": 44,
            "patient_gender": "F",
            "admission_type": "day_care",
            "planned_admission_date": admission.isoformat(),
            "diagnosis_text": "Synthetic cataract diagnosis",
            "procedure_text": "Phacoemulsification with IOL",
            "procedure_code": "SYN-001",
            "room_category_requested": "single",
            "estimated_cost": 75000,
            "hospital_id": "SYN-HOSP-LOAD",
            "prior_conditions": [],
            "notes": "Synthetic load test",
        }

    @task(9)
    def valid_run(self) -> None:
        started = time.perf_counter()
        headers = {"X-Client-ID": self.client_id}
        with self.client.post(
            "/v1/preauth",
            json=self.payload(),
            headers=headers,
            name="POST /v1/preauth",
            catch_response=True,
        ) as accepted:
            if accepted.status_code != 202:
                accepted.failure(f"submission status {accepted.status_code}")
                return
            poll_url = accepted.json()["poll_url"]
        terminal = None
        for _ in range(600):
            response = self.client.get(poll_url, name="GET /v1/runs/:id")
            if response.status_code != 200:
                break
            terminal = response.json()
            if terminal["status"] in TERMINAL:
                break
            time.sleep(0.05)
        elapsed_ms = (time.perf_counter() - started) * 1000
        success = terminal is not None and terminal.get("status") in TERMINAL
        events.request.fire(
            request_type="E2E",
            name="preauth terminal",
            response_time=elapsed_ms,
            response_length=0,
            exception=None if success else RuntimeError("run did not reach terminal state"),
            context={},
        )

    @task(1)
    def malformed_is_quarantined(self) -> None:
        payload = self.payload()
        payload["patient_age"] = 999
        with self.client.post(
            "/v1/preauth",
            json=payload,
            headers={"X-Client-ID": self.client_id},
            name="POST /v1/preauth malformed",
            catch_response=True,
        ) as response:
            if response.status_code == 422:
                response.success()
            else:
                response.failure(f"expected 422, got {response.status_code}")
