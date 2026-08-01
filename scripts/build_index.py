"""오프라인 인덱스 빌드: JSONL -> Chroma 영속 컬렉션."""
from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.embedding import KureEmbedder
from bible_search.indexer import build_index


def main() -> None:
    s = get_settings()
    verses = load_verses(s.data_path)
    print(f"loaded {len(verses)} verses from {s.data_path}")
    embedder = KureEmbedder(s.embedding_model)
    count = build_index(verses, embedder, s.chroma_path, s.chroma_collection)
    print(f"indexed {count} verses into {s.chroma_path}/{s.chroma_collection}")


if __name__ == "__main__":
    main()
