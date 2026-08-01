import chromadb
from bible_search.models import Verse
from bible_search.embedding import Embedder
from bible_search.retrievers.dense import add_verses_to_collection


def build_index(verses: list[Verse], embedder: Embedder,
                chroma_path: str, collection_name: str) -> int:
    client = chromadb.PersistentClient(chroma_path)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )
    add_verses_to_collection(collection, verses, embedder)
    return collection.count()
