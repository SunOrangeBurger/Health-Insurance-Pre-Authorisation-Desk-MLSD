import json
from datetime import date, timedelta
from pathlib import Path

import faiss
import numpy as np
import pytest

from preauth.agents.graph import PreauthAgentSystem
from preauth.agents.models import EvidenceBundle
from preauth.agents.verifier import resolve_citations
from preauth.config import Settings
from preauth.rag.embeddings import HashingEmbedder
from preauth.rag.models import Chunk, SearchResult


def make_agent_index(path: Path) -> HashingEmbedder:
    chunks = [
        Chunk(chunk_id="cover", doc_id="policy", clause_id="B.1.1", section="Benefits", page=11, text="The Company shall indemnify Hospitalization Expenses including All Day Care Treatments up to the Sum Insured.", provision_type="cover", content_hash="1"),
        Chunk(chunk_id="wait", doc_id="policy", clause_id="C.1.b", section="Waiting Periods", page=31, text="Cataract and other disorders of lens and Retina are excluded until expiry of 24 months of continuous coverage.", provision_type="waiting_period", content_hash="2"),
        Chunk(chunk_id="exclude", doc_id="policy", clause_id="C.2", section="Exclusions", page=33, text="Permanent exclusions apply only as listed in this policy.", provision_type="exclusion", content_hash="3"),
        Chunk(chunk_id="room", doc_id="policy", clause_id="B.1.1.note", section="Benefits", page=12, text="Room Rent above eligibility causes proportionate deduction.", provision_type="room_rent", content_hash="4"),
        Chunk(chunk_id="limit", doc_id="policy", clause_id="Def.28", section="Definitions", page=10, text="Sub-limit means a maximum amount specified in the Policy Schedule.", provision_type="sublimit", content_hash="5"),
    ]
    path.mkdir()
    (path / "chunks.json").write_text(json.dumps([chunk.model_dump() for chunk in chunks]))
    embedder = HashingEmbedder()
    vectors = embedder.encode([chunk.text for chunk in chunks])
    np.save(path / "vectors.npy", vectors)
    index = faiss.IndexFlatIP(embedder.dimension)
    index.add(vectors)
    faiss.write_index(index, str(path / "index.faiss"))
    return embedder


def request_for_months(months: int, procedure: str = "Phacoemulsification for cataract") -> dict:
    admission = date.today() + timedelta(days=7)
    return {
        "admission_type": "day_care",
        "diagnosis_text": "Cataract right eye" if "cataract" in procedure.lower() else procedure,
        "procedure_text": procedure,
        "prior_conditions": [],
        "policy_start_date": str(admission - timedelta(days=round(months * 30.4375))),
        "planned_admission_date": str(admission),
        "sum_insured": 500_000,
        "estimated_cost": 75_000,
    }


def settings(**overrides) -> Settings:
    values = {"max_steps": 12, "max_tool_calls": 10, "max_replans": 2, "tool_timeout_s": 5, "run_timeout_s": 30}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.asyncio
async def test_cataract_reference_case_retrieves_cover_and_waiting_clause(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = make_agent_index(index_dir)
    system = PreauthAgentSystem.from_index(index_dir, embedder, settings())
    result, trace = await system.run(request_for_months(11))
    assert result.route == "medical-review"
    assert result.coverage_position == "waiting_period_not_served"
    assert result.verification.passed is True
    assert {citation["id"] for citation in result.citations} == {"B.1.1", "C.1.b"}
    assert any(event.agent == "verifier-router" for event in trace)


@pytest.mark.asyncio
async def test_reference_variant_flips_after_waiting_period(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = make_agent_index(index_dir)
    system = PreauthAgentSystem.from_index(index_dir, embedder, settings())
    result, _ = await system.run(request_for_months(30))
    assert result.route == "approve-recommended"
    assert result.coverage_position == "waiting_period_served"


@pytest.mark.asyncio
async def test_out_of_corpus_procedure_escalates_without_citations(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = make_agent_index(index_dir)
    system = PreauthAgentSystem.from_index(index_dir, embedder, settings())
    result, _ = await system.run(request_for_months(30, "Quantum neural transplant"))
    assert result.route == "medical-review"
    assert result.verification.passed is False


@pytest.mark.asyncio
async def test_fake_citation_is_caught_and_bounded(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = make_agent_index(index_dir)
    system = PreauthAgentSystem.from_index(index_dir, embedder, settings())
    request = request_for_months(30)
    request["_force_bad_citation"] = True
    result, trace = await system.run(request)
    assert result.route == "medical-review"
    assert result.verification.passed is False
    assert any("missing citations" in check for check in result.verification.checks)
    tool_calls = [event for event in trace if event.kind == "tool_call"]
    assert len(tool_calls) <= 10


@pytest.mark.asyncio
async def test_tool_loop_is_cut_by_limit(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = make_agent_index(index_dir)
    system = PreauthAgentSystem.from_index(index_dir, embedder, settings(max_tool_calls=2))
    result, trace = await system.run(request_for_months(30))
    assert result.route == "medical-review"
    assert len([event for event in trace if event.kind == "tool_call"]) == 2


def test_deterministic_citation_resolution_rejects_unknown_id() -> None:
    passage = SearchResult(chunk_id="real", doc_id="policy", clause_id="B.1.1", section="Benefits", page=11, text="cover", provision_type="cover", content_hash="x", score=1, rank_sources=[])
    bundle = EvidenceBundle(admission_class="day_care", entities={}, passages=[passage], claimed_citation_ids=["fake"])
    valid, missing = resolve_citations(bundle)
    assert valid is False
    assert missing == ["fake"]
