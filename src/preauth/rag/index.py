import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from preauth.rag.chunking import CHUNKER_VERSION, extract_pdf_chunks
from preauth.rag.embeddings import Embedder
from preauth.rag.models import Chunk, IndexManifest


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IndexBuilder:
    def __init__(self, output_dir: Path, embedder: Embedder) -> None:
        self.output_dir = output_dir
        self.embedder = embedder

    def build(self, documents: list[Path], only_doc_id: str | None = None) -> IndexManifest:
        started = time.perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = self.output_dir / "chunks.json"
        vectors_path = self.output_dir / "vectors.npy"
        old_chunks = self._load_chunks(chunks_path)
        old_vectors = self._load_vectors(vectors_path, len(old_chunks))
        retained: list[Chunk] = []
        retained_vectors: list[np.ndarray] = []
        target_ids = {only_doc_id} if only_doc_id else {path.stem for path in documents}
        for chunk, vector in zip(old_chunks, old_vectors, strict=False):
            if chunk.doc_id not in target_ids:
                retained.append(chunk)
                retained_vectors.append(vector)
        selected = [path for path in documents if not only_doc_id or path.stem == only_doc_id]
        if only_doc_id and not selected:
            raise ValueError(f"unknown document: {only_doc_id}")
        new_chunks = [chunk for path in selected for chunk in extract_pdf_chunks(path)]
        new_vectors = self.embedder.encode([self._embedding_text(chunk) for chunk in new_chunks]) if new_chunks else np.empty((0, self.embedder.dimension), dtype="float32")
        all_chunks = retained + new_chunks
        vector_parts = retained_vectors + [vector for vector in new_vectors]
        all_vectors = np.asarray(vector_parts, dtype="float32") if vector_parts else np.empty((0, self.embedder.dimension), dtype="float32")
        chunks_path.write_text(json.dumps([chunk.model_dump() for chunk in all_chunks], indent=2) + "\n", encoding="utf-8")
        np.save(vectors_path, all_vectors)
        index = faiss.IndexFlatIP(self.embedder.dimension)
        if len(all_vectors):
            index.add(all_vectors)
        faiss.write_index(index, str(self.output_dir / "index.faiss"))
        elapsed = max(time.perf_counter() - started, 1e-9)
        manifest = IndexManifest(
            built_at=datetime.now(timezone.utc).isoformat(),
            documents=[
                {"doc_id": path.stem, "filename": path.name, "sha256": _file_sha256(path)}
                for path in documents
            ],
            n_chunks=len(all_chunks),
            embedding_model=self.embedder.name,
            chunker_version=CHUNKER_VERSION,
            build_seconds=round(elapsed, 6),
            chunks_per_second=round(len(new_chunks) / elapsed, 3),
        )
        (self.output_dir / "index_manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return manifest

    @staticmethod
    def _embedding_text(chunk: Chunk) -> str:
        return f"[{chunk.section} | {chunk.clause_id} | {chunk.provision_type}] {chunk.text}"

    @staticmethod
    def _load_chunks(path: Path) -> list[Chunk]:
        if not path.exists():
            return []
        return [Chunk.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]

    def _load_vectors(self, path: Path, expected: int) -> np.ndarray:
        if not path.exists() or expected == 0:
            return np.empty((0, self.embedder.dimension), dtype="float32")
        vectors = np.load(path)
        if len(vectors) != expected or vectors.shape[1] != self.embedder.dimension:
            return np.empty((0, self.embedder.dimension), dtype="float32")
        return vectors
