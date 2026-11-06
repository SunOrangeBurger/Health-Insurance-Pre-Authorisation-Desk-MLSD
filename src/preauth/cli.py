import argparse
from pathlib import Path

from preauth.config import get_settings
from preauth.rag.embeddings import HashingEmbedder, MiniLMEmbedder
from preauth.rag.index import IndexBuilder


def ingest(args: argparse.Namespace) -> int:
    settings = get_settings()
    raw_dir = Path(settings.corpus_raw_dir)
    documents = sorted(raw_dir.glob("*.pdf"))
    if not documents:
        raise SystemExit(f"no PDF files found in {raw_dir}")
    embedder = HashingEmbedder() if args.embedding_backend == "hashing" else MiniLMEmbedder(settings.local_embedding_model)
    manifest = IndexBuilder(Path(settings.index_storage_dir), embedder).build(documents, only_doc_id=args.only)
    print(manifest.model_dump_json(indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m preauth.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--reembed", action="store_true", help="Recompute vectors for selected documents")
    ingest_parser.add_argument("--only", help="Document ID (filename without .pdf)")
    ingest_parser.add_argument("--embedding-backend", choices=("minilm", "hashing"), default="minilm")
    ingest_parser.set_defaults(handler=ingest)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
