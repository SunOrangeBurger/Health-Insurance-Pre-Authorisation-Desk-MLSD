import json
from collections import OrderedDict
from pathlib import Path

import faiss
from rank_bm25 import BM25Okapi

from preauth.rag.embeddings import Embedder
from preauth.rag.models import Chunk, SearchResult
from prometheus_client import Counter


RETRIEVAL_CACHE = Counter("retrieval_cache_requests_total", "Retrieval cache requests", ["outcome"])


class HybridRetriever:
    def __init__(self, index_dir: Path, embedder: Embedder, *, cache_enabled: bool = True, cache_size: int = 512) -> None:
        self.embedder = embedder
        self.chunks = [
            Chunk.model_validate(item)
            for item in json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
        ]
        self.index = faiss.read_index(str(index_dir / "index.faiss"))
        self.bm25 = BM25Okapi([self._tokens(chunk.text) for chunk in self.chunks])
        manifest_path = index_dir / "index_manifest.json"
        self.index_version = (
            json.loads(manifest_path.read_text(encoding="utf-8"))["built_at"]
            if manifest_path.exists()
            else str((index_dir / "chunks.json").stat().st_mtime_ns)
        )
        self.cache_enabled = cache_enabled
        self.cache_size = cache_size
        self._cache: OrderedDict[tuple[str, str | None, int, str], list[SearchResult]] = OrderedDict()

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.strip(".,:;()[]\"'").lower() for token in text.split() if token.strip()]

    def search(self, query: str, provision_type: str | None = None, top_k: int = 5) -> list[SearchResult]:
        key = (query.strip().lower(), provision_type, top_k, self.index_version)
        if self.cache_enabled and key in self._cache:
            RETRIEVAL_CACHE.labels("hit").inc()
            self._cache.move_to_end(key)
            return [item.model_copy(deep=True) for item in self._cache[key]]
        RETRIEVAL_CACHE.labels("miss").inc()
        allowed = {
            index
            for index, chunk in enumerate(self.chunks)
            if provision_type is None or chunk.provision_type == provision_type
        }
        if not allowed:
            return []
        fetch_k = min(max(top_k * 6, 20), len(self.chunks))
        query_vector = self.embedder.encode([query])
        _, dense_indices = self.index.search(query_vector, fetch_k)
        dense_rank = [int(index) for index in dense_indices[0] if int(index) in allowed]
        bm25_scores = self.bm25.get_scores(self._tokens(query))
        sparse_rank = sorted(allowed, key=lambda index: float(bm25_scores[index]), reverse=True)
        scores: dict[int, float] = {}
        sources: dict[int, list[str]] = {}
        for source, ranking in (("dense", dense_rank), ("bm25", sparse_rank)):
            for rank, index in enumerate(ranking[:fetch_k], start=1):
                scores[index] = scores.get(index, 0.0) + 1.0 / (60 + rank)
                sources.setdefault(index, []).append(source)
        query_tokens = set(self._tokens(query))
        for index in allowed:
            text_tokens = set(self._tokens(self.chunks[index].text))
            if query_tokens and query_tokens.issubset(text_tokens):
                scores[index] = scores.get(index, 0.0) + 0.05
                sources.setdefault(index, []).append("exact")
        ranked = sorted(scores, key=scores.get, reverse=True)[:top_k]
        results = [
            SearchResult(**self.chunks[index].model_dump(), score=scores[index], rank_sources=sources[index])
            for index in ranked
        ]
        if self.cache_enabled:
            self._cache[key] = [item.model_copy(deep=True) for item in results]
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return results

    def get_clause(self, clause_id: str) -> list[SearchResult]:
        return [
            SearchResult(**chunk.model_dump(), score=1.0, rank_sources=["clause_id"])
            for chunk in self.chunks
            if chunk.clause_id == clause_id
        ]
