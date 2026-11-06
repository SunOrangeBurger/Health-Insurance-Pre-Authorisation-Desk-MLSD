import json
from pathlib import Path

import fitz
import numpy as np

from preauth.rag.chunking import classify_provision, extract_pdf_chunks
from preauth.rag.embeddings import HashingEmbedder
from preauth.rag.index import IndexBuilder
from preauth.rag.retriever import HybridRetriever


def make_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 780), text, fontsize=10)
    document.save(path)
    document.close()


def test_provision_classification() -> None:
    assert classify_provision("Specified disease waiting period is 24 months") == "waiting_period"
    assert classify_provision("Room Rent proportionate deduction applies") == "room_rent"
    assert classify_provision("The Company shall indemnify this benefit") == "cover"


def test_idempotent_index_and_hybrid_search(tmp_path: Path) -> None:
    raw = tmp_path / "policy.pdf"
    make_pdf(
        raw,
        [
            "SECTION B. BENEFITS\n1.1. Hospitalization Expenses\nThe Company shall indemnify medical expenses.\nAll Day Care Treatments.",
            "SECTION C. WAITING PERIODS AND EXCLUSIONS\nb. Specified Disease/Procedure waiting period\nCataract is excluded until expiry of 24 months continuous coverage.",
        ],
    )
    output = tmp_path / "index"
    embedder = HashingEmbedder()
    first = IndexBuilder(output, embedder).build([raw])
    first_chunks = json.loads((output / "chunks.json").read_text())
    second = IndexBuilder(output, embedder).build([raw])
    second_chunks = json.loads((output / "chunks.json").read_text())
    assert first.n_chunks == second.n_chunks
    assert [item["chunk_id"] for item in first_chunks] == [item["chunk_id"] for item in second_chunks]
    retriever = HybridRetriever(output, embedder)
    results = retriever.search("cataract", provision_type="waiting_period")
    assert results
    assert "Cataract" in results[0].text


def test_incremental_reembed_preserves_other_document_vectors(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_pdf(first, ["SECTION B. BENEFITS\n1.1. Hospitalization benefit shall indemnify expenses."])
    make_pdf(second, ["SECTION C. WAITING PERIODS\nCataract waiting period is 24 months."])
    output = tmp_path / "index"
    embedder = HashingEmbedder()
    builder = IndexBuilder(output, embedder)
    builder.build([first, second])
    chunks_before = json.loads((output / "chunks.json").read_text())
    vectors_before = np.load(output / "vectors.npy")
    preserved = {
        chunk["chunk_id"]: vectors_before[index].copy()
        for index, chunk in enumerate(chunks_before)
        if chunk["doc_id"] == "second"
    }
    builder.build([first, second], only_doc_id="first")
    chunks_after = json.loads((output / "chunks.json").read_text())
    vectors_after = np.load(output / "vectors.npy")
    for index, chunk in enumerate(chunks_after):
        if chunk["doc_id"] == "second":
            assert np.array_equal(vectors_after[index], preserved[chunk["chunk_id"]])


def test_actual_policy_reference_clauses_are_extracted() -> None:
    policy = Path("corpus/raw/optima_secure_policy_wording.pdf")
    if not policy.exists():
        return
    chunks = extract_pdf_chunks(policy)
    by_clause = {chunk.clause_id: chunk for chunk in chunks}
    assert "B.1.1" in by_clause
    assert "C.1.b" in by_clause
    assert "cataract" in by_clause["C.1.b"].text.lower()
    assert "expiry of 24 months" in by_clause["C.1.b"].text.lower()
    assert "expiry of 36 months" not in by_clause["C.1.b"].text.lower()
    assert by_clause["C.1.b"].provision_type == "waiting_period"
