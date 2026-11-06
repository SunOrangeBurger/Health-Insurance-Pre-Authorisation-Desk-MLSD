import json
from pathlib import Path

from preauth.api.main import app
from preauth.api.schemas import (
    FeedbackRequest,
    LLMRequest,
    LLMResponse,
    PreauthRequest,
    QueueJobMessage,
    RunResponse,
    SubmissionResponse,
)

OUTPUT = Path("contracts")
OUTPUT.mkdir(exist_ok=True)

schemas = {
    "preauth_request.schema.json": PreauthRequest.model_json_schema(),
    "preauth_submission.schema.json": SubmissionResponse.model_json_schema(),
    "run_response.schema.json": RunResponse.model_json_schema(),
    "queue_job.schema.json": QueueJobMessage.model_json_schema(),
    "feedback_request.schema.json": FeedbackRequest.model_json_schema(),
    "llm_request.schema.json": LLMRequest.model_json_schema(),
    "llm_response.schema.json": LLMResponse.model_json_schema(),
    "openapi.json": app.openapi(),
}

for filename, schema in schemas.items():
    (OUTPUT / filename).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
