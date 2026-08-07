import chromadb
from bible_search.config import Settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer
from bible_search.embedding import Embedder, HfApiEmbedder, KureEmbedder
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.search_service import SearchService


def _make_embedder(settings: Settings) -> Embedder:
    if settings.embedder == "local":
        return KureEmbedder(settings.embedding_model)
    if settings.embedder == "hf":
        return HfApiEmbedder(settings.embedding_model, token=settings.hf_token)
    raise ValueError(
        f"알 수 없는 embedder 설정: {settings.embedder!r} "
        "(유효한 값: 'local', 'hf')"
    )


def build_search_service(settings: Settings,
                         embedder: Embedder | None = None) -> SearchService:
    verses = load_verses(settings.data_path)
    if embedder is None:
        embedder = _make_embedder(settings)

    client = chromadb.PersistentClient(settings.chroma_path)
    collection = client.get_collection(settings.chroma_collection)

    exact = ExactMatcher(verses)
    bm25 = BM25Retriever(verses, KiwiTokenizer())
    dense = DenseRetriever(collection, verses, embedder,
                           threshold=settings.dense_threshold)
    return SearchService(exact, bm25, dense,
                         rrf_k=settings.rrf_k, max_results=settings.max_results,
                         bm25_top_k=settings.bm25_top_k)
