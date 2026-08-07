from pathlib import Path

import chromadb
from bible_search.config import Settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer
from bible_search.token_cache import load_token_cache
from bible_search.embedding import Embedder, HfApiEmbedder, KureEmbedder
from bible_search.models import Verse
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.search_service import SearchService
from bible_search.vectorstore import NumpyDenseRetriever, load_numpy_index


def _make_embedder(settings: Settings) -> Embedder:
    if settings.embedder == "local":
        return KureEmbedder(settings.embedding_model)
    if settings.embedder == "hf":
        return HfApiEmbedder(settings.embedding_model, token=settings.hf_token)
    raise ValueError(
        f"알 수 없는 embedder 설정: {settings.embedder!r} "
        "(유효한 값: 'local', 'hf')"
    )


def _make_dense_retriever(settings: Settings, verses: list[Verse],
                          embedder: Embedder) -> DenseRetriever | NumpyDenseRetriever:
    if settings.vector_store == "chroma":
        client = chromadb.PersistentClient(settings.chroma_path)
        collection = client.get_collection(settings.chroma_collection)
        return DenseRetriever(collection, verses, embedder,
                              threshold=settings.dense_threshold)
    if settings.vector_store == "numpy":
        vectors, ids = load_numpy_index(settings.numpy_index_path)
        return NumpyDenseRetriever(vectors, ids, verses, embedder,
                                   threshold=settings.dense_threshold)
    raise ValueError(
        f"알 수 없는 vector_store 설정: {settings.vector_store!r} "
        "(유효한 값: 'chroma', 'numpy')"
    )


def _make_bm25_retriever(settings: Settings, verses: list[Verse],
                         tokenizer: KiwiTokenizer) -> BM25Retriever:
    if not settings.use_token_cache:
        return BM25Retriever(verses, tokenizer)

    cache_path = Path(settings.token_cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"토큰 캐시 파일이 없습니다: {cache_path}. "
            "먼저 `python scripts/build_token_cache.py`를 실행해 캐시를 생성하세요."
        )
    corpus = load_token_cache(cache_path, verses)
    return BM25Retriever(verses, tokenizer, corpus=corpus)


def build_search_service(settings: Settings,
                         embedder: Embedder | None = None) -> SearchService:
    verses = load_verses(settings.data_path)
    if embedder is None:
        embedder = _make_embedder(settings)

    exact = ExactMatcher(verses)
    bm25 = _make_bm25_retriever(settings, verses, KiwiTokenizer())
    dense = _make_dense_retriever(settings, verses, embedder)
    return SearchService(exact, bm25, dense,
                         rrf_k=settings.rrf_k, max_results=settings.max_results,
                         bm25_top_k=settings.bm25_top_k)
