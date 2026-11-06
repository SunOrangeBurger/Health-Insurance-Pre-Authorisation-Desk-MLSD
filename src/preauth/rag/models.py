from typing import Any, Literal

from pydantic import BaseModel, Field


ProvisionType = Literal[
    "cover",
    "waiting_period",
    "exclusion",
    "sublimit",
    "room_rent",
    "definition",
    "claims_procedure",
    "day_care_list",
    "other",
]


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    clause_id: str
    section: str
    page: int = Field(ge=1)
    text: str
    provision_type: ProvisionType
    content_hash: str


class SearchResult(Chunk):
    score: float
    rank_sources: list[str] = Field(default_factory=list)


class IndexManifest(BaseModel):
    built_at: str
    documents: list[dict[str, Any]]
    n_chunks: int
    embedding_model: str
    chunker_version: str
    build_seconds: float
    chunks_per_second: float
