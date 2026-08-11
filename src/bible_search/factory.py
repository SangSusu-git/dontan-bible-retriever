from pathlib import Path

from bible_search.config import Settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer, MecabTokenizer
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


def _make_tokenizer(settings: Settings) -> KiwiTokenizer | MecabTokenizer:
    if settings.tokenizer == "kiwi":
        return KiwiTokenizer()
    if settings.tokenizer == "mecab":
        return MecabTokenizer()
    raise ValueError(
        f"알 수 없는 tokenizer 설정: {settings.tokenizer!r} "
        "(유효한 값: 'kiwi', 'mecab')"
    )


def _make_dense_retriever(settings: Settings, verses: list[Verse],
                          embedder: Embedder) -> DenseRetriever | NumpyDenseRetriever:
    if settings.vector_store == "chroma":
        # chromadb는 무거운 의존성이라, numpy 저장소만 쓰는 경량 배포에서는
        # 설치조차 하지 않는다. 그래서 최상위가 아니라 이 분기에서 import한다.
        import chromadb

        client = chromadb.PersistentClient(settings.chroma_path)
        collection = client.get_collection(settings.chroma_collection)
        return DenseRetriever(collection, verses, embedder,
                              threshold=settings.dense_threshold)
    if settings.vector_store == "numpy":
        vectors, ids, basis = load_numpy_index(settings.numpy_index_path)
        return NumpyDenseRetriever(vectors, ids, verses, embedder,
                                   threshold=settings.dense_threshold, basis=basis)
    raise ValueError(
        f"알 수 없는 vector_store 설정: {settings.vector_store!r} "
        "(유효한 값: 'chroma', 'numpy')"
    )


def _make_bm25_retriever(settings: Settings, verses: list[Verse],
                         tokenizer: KiwiTokenizer | MecabTokenizer) -> BM25Retriever:
    if not settings.use_token_cache:
        return BM25Retriever(verses, tokenizer, b=settings.bm25_b)

    cache_path = Path(settings.token_cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"토큰 캐시 파일이 없습니다: {cache_path}. "
            "먼저 `python scripts/build_token_cache.py`를 실행해 캐시를 생성하세요."
        )
    # tokenizer를 넘겨, 다른 토크나이저로 만든 캐시를 조용히 잘못 쓰지
    # 않도록 이름 불일치를 검증한다.
    corpus = load_token_cache(cache_path, verses, tokenizer=tokenizer)
    return BM25Retriever(verses, tokenizer, corpus=corpus, b=settings.bm25_b)


def build_search_service(settings: Settings,
                         embedder: Embedder | None = None) -> SearchService:
    verses = load_verses(settings.data_path)
    if embedder is None:
        embedder = _make_embedder(settings)

    exact = ExactMatcher(verses)
    bm25 = _make_bm25_retriever(settings, verses, _make_tokenizer(settings))
    dense = _make_dense_retriever(settings, verses, embedder)
    return SearchService(exact, bm25, dense,
                         rrf_k=settings.rrf_k, max_results=settings.max_results,
                         bm25_top_k=settings.bm25_top_k, fusion=settings.fusion,
                         w_bm25=settings.w_bm25, w_dense=settings.w_dense,
                         w_cov=settings.w_cov, w_prox=settings.w_prox)
