import hashlib
import re
from pathlib import Path

import fitz

from preauth.rag.models import Chunk

CHUNKER_VERSION = "clause-aware-v1"
HEADER_FOOTER_PATTERNS = (
    "HDFC ERGO General Insurance Company Limited",
    "Policy Wording",
    "my: Optima Secure",
    "UIN: my: Optima Secure",
    "IRDAI Reg. No.",
)


def _normalise(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or any(marker in line for marker in HEADER_FOOTER_PATTERNS):
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _section_for(page: int, text: str) -> str:
    upper = text.upper()
    if "SECTION B" in upper or 11 <= page <= 29:
        return "SECTION B — BENEFITS"
    if "SECTION C" in upper or 30 <= page <= 44:
        return "SECTION C — WAITING PERIODS AND EXCLUSIONS"
    if "SECTION D" in upper or 45 <= page <= 48:
        return "SECTION D — GENERAL EXCLUSIONS"
    if "SECTION E" in upper or page >= 49:
        return "SECTION E — CLAIMS AND GENERAL TERMS"
    return "DEFINITIONS"


def _canonical_clause_id(section: str, page: int, text: str, ordinal: int) -> str:
    lowered = text.lower()
    if page in {11, 12} and ("hospitalization expenses" in lowered or "all day care treatments" in lowered):
        return "B.1.1"
    if page == 30 and "pre-existing diseases" in lowered:
        return "C.1.a"
    if page in {30, 31} and ("specified disease/procedure" in lowered or "cataract" in lowered):
        return "C.1.b"
    if page in {31, 32} and "30-day waiting period" in lowered:
        return "C.1.c"
    match = re.match(r"^(Def\.\s*\d+|\d+(?:\.\d+){1,3})[.\s]", text)
    if match:
        raw = match.group(1).replace(" ", "").rstrip(".")
        prefix = "B" if "SECTION B" in section else "C" if "SECTION C" in section else "E" if "SECTION E" in section else "D"
        return raw if raw.startswith("Def") else f"{prefix}.{raw}"
    prefix = "B" if "SECTION B" in section else "C" if "SECTION C" in section else "E" if "SECTION E" in section else "D"
    return f"{prefix}.p{page}.{ordinal}"


def classify_provision(text: str) -> str:
    lowered = text.lower()
    if "waiting period" in lowered or "continuous coverage" in lowered:
        return "waiting_period"
    if "day care" in lowered and ("treatment" in lowered or "procedure" in lowered):
        return "day_care_list"
    if "room rent" in lowered or "proportionate deduction" in lowered or "room category" in lowered:
        return "room_rent"
    if "sub-limit" in lowered or "sublimit" in lowered:
        return "sublimit"
    if "exclusion" in lowered or "excluded" in lowered or "not covered" in lowered:
        return "exclusion"
    if "claim" in lowered and ("procedure" in lowered or "notification" in lowered):
        return "claims_procedure"
    if text.startswith("Def.") or " means " in lowered:
        return "definition"
    if any(term in lowered for term in ("shall indemnify", "base coverage", "cover shall", "benefit")):
        return "cover"
    return "other"


def _split_page(text: str, max_chars: int = 1800) -> list[str]:
    paragraphs = re.split(r"\n(?=(?:Def\.\s*\d+|\d+(?:\.\d+)+|[a-z]\.)\s)", text)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) > max_chars:
            chunks.append(current.strip())
            current = ""
        current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


def extract_pdf_chunks(path: Path, doc_id: str | None = None) -> list[Chunk]:
    document_id = doc_id or path.stem
    chunks: list[Chunk] = []
    with fitz.open(path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            page_text = _normalise(page.get_text("text"))
            if not page_text:
                continue
            section = _section_for(page_index, page_text)
            for ordinal, text in enumerate(_split_page(page_text), start=1):
                clause_id = _canonical_clause_id(section, page_index, text, ordinal)
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                stable = f"{document_id}|{clause_id}|{page_index}|{content_hash}"
                chunk_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        doc_id=document_id,
                        clause_id=clause_id,
                        section=section,
                        page=page_index,
                        text=text,
                        provision_type=classify_provision(text),
                        content_hash=content_hash,
                    )
                )
    return _merge_reference_clauses(chunks)


def _merge_reference_clauses(chunks: list[Chunk]) -> list[Chunk]:
    """Keep policy clauses split across adjacent PDF pages retrievable as one unit."""
    reference_ids = {"B.1.1", "C.1.a", "C.1.b", "C.1.c"}
    merged: list[Chunk] = []
    for clause_id in reference_ids:
        matches = [chunk for chunk in chunks if chunk.clause_id == clause_id]
        if not matches:
            continue
        text = "\n".join(dict.fromkeys(chunk.text for chunk in matches))
        markers = {
            "C.1.a": "Pre-Existing Diseases",
            "C.1.b": "Specified Disease/Procedure waiting period",
            "C.1.c": "30-day waiting period",
            "B.1.1": "Hospitalization Expenses",
        }
        marker = markers[clause_id]
        marker_index = text.lower().find(marker.lower())
        if marker_index >= 0:
            text = text[marker_index:]
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        first = min(matches, key=lambda item: item.page)
        stable = f"{first.doc_id}|{clause_id}|{first.page}|{content_hash}"
        merged.append(
            first.model_copy(
                update={
                    "chunk_id": hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24],
                    "text": text,
                    "content_hash": content_hash,
                    "provision_type": "cover" if clause_id == "B.1.1" else "waiting_period",
                }
            )
        )
    return [chunk for chunk in chunks if chunk.clause_id not in reference_ids] + merged
