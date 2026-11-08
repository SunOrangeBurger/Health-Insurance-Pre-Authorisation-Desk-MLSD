import re
from dataclasses import dataclass, field
from typing import Any


FREE_TEXT_FIELDS = ("diagnosis_text", "procedure_text", "prior_conditions", "notes")
INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b", re.I),
    re.compile(r"\b(system|developer)\s+prompt\b", re.I),
    re.compile(r"\b(disregard|override|bypass)\b.{0,40}\b(instructions?|rules?|guardrails?)\b", re.I),
    re.compile(r"\b(do|must)\s+not\s+(use|call|search)\s+(the\s+)?tools?\b", re.I),
    re.compile(r"\b(reveal|print|repeat|exfiltrate)\b.{0,40}\b(prompt|secret|key|token)\b", re.I),
    re.compile(r"\b(approve|authorise|authorize|deny|reject)\s+(this|the)\s+(claim|request)\b", re.I),
    re.compile(r"\bact\s+as\b.{0,40}\b(system|administrator|insurer)\b", re.I),
    re.compile(r"<\s*/?\s*(system|assistant|tool|prompt)\s*>", re.I),
    re.compile(r"\bexecute\b.{0,40}\b(command|code|shell|sql)\b", re.I),
    re.compile(r"\bforget\b.{0,30}\b(instructions?|rules?|policy)\b", re.I),
)
TOXIC_TERMS = re.compile(
    r"\b(kill yourself|go die|worthless (?:idiot|person)|racial slur|terrorist scum)\b", re.I
)
PROHIBITED_DETERMINATIONS = re.compile(
    r"\b(approved|authorised|authorized|denied|rejected)\b", re.I
)


@dataclass
class GuardrailFinding:
    field: str
    categories: list[str] = field(default_factory=list)


def inspect_text(field_name: str, value: str) -> GuardrailFinding | None:
    categories: list[str] = []
    if any(pattern.search(value) for pattern in INJECTION_PATTERNS):
        categories.append("prompt_injection")
    if TOXIC_TERMS.search(value):
        categories.append("toxicity")
    return GuardrailFinding(field_name, categories) if categories else None


def inspect_request(payload: dict[str, Any]) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    for name in FREE_TEXT_FIELDS:
        value = payload.get(name)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and (finding := inspect_text(name, item)):
                findings.append(finding)
                break
    return findings


def sanitize_output(value: Any) -> Any:
    """Remove prohibited determination language without changing structured routes."""
    if isinstance(value, str):
        value = PROHIBITED_DETERMINATIONS.sub("final-decision", value)
        if TOXIC_TERMS.search(value):
            return "Output withheld by the safety filter."
        return value
    if isinstance(value, list):
        return [sanitize_output(item) for item in value]
    if isinstance(value, dict):
        return {
            key: item if key in {"citations", "route", "coverage_position"} else sanitize_output(item)
            for key, item in value.items()
        }
    return value
