import pytest
from fastapi.testclient import TestClient

from bible_search.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch, fake_embedder):
    from pathlib import Path
    src = Path(__file__).parent / "data" / "verses_fixture.jsonl"
    data_path = tmp_path / "verses.jsonl"
    data_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    chroma_path = str(tmp_path / "chroma")

    monkeypatch.setenv("BIBLE_API_KEY", "testkey")
    monkeypatch.setenv("BIBLE_DATA_PATH", str(data_path))
    monkeypatch.setenv("BIBLE_CHROMA_PATH", chroma_path)
    monkeypatch.setenv("BIBLE_DENSE_THRESHOLD", "0.5")

    from bible_search.data.loader import load_verses
    from bible_search.indexer import build_index
    from bible_search.factory import build_search_service
    settings = Settings()
    verses = load_verses(settings.data_path)
    build_index(verses, fake_embedder, settings.chroma_path, settings.chroma_collection)
    service = build_search_service(settings, embedder=fake_embedder)

    from bible_search.api import app, get_settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.service = service
    return TestClient(app)


def test_health_no_auth(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_search_requires_api_key(client):
    r = client.post("/search", json={"query": "여호와"})
    assert r.status_code == 401


def test_search_wrong_api_key(client):
    r = client.post("/search", json={"query": "여호와"}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_search_returns_sections(client):
    r = client.post("/search", json={"query": "천지를 창조"},
                    headers={"X-API-Key": "testkey"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "천지를 창조"
    exact_ids = [m["id"] for m in body["exact_matches"]]
    assert "개역개정:창세기:1:1" in exact_ids
    assert "source" in body["exact_matches"][0]
