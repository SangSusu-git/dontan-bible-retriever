from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends, Request
from pydantic import BaseModel

from bible_search.config import Settings, get_settings
from bible_search.factory import build_search_service
from bible_search.models import SearchResult


class SearchRequest(BaseModel):
    query: str


def _serialize(r: SearchResult) -> dict:
    v = r.verse
    return {
        "id": v.id, "book": v.book, "chapter": v.chapter, "verse": v.verse,
        "text": v.text, "translation": v.translation,
        "score": r.score, "source": r.source,
    }


def _require_api_key(x_api_key: str | None, settings: Settings) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 테스트에서 app.state.service를 미리 주입한 경우 재구성하지 않는다
    if not getattr(app.state, "service", None):
        app.state.service = build_search_service(get_settings())
    yield


app = FastAPI(title="Bible Hybrid Search", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/search")
def search(req: SearchRequest, request: Request,
           x_api_key: str | None = Header(default=None),
           settings: Settings = Depends(get_settings)) -> dict:
    _require_api_key(x_api_key, settings)
    resp = request.app.state.service.search(req.query)
    return {
        "query": req.query,
        "exact_matches": [_serialize(r) for r in resp.exact_matches],
        "related_matches": [_serialize(r) for r in resp.related_matches],
    }
