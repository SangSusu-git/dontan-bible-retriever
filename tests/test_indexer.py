import chromadb
from bible_search.indexer import build_index


def test_build_index_persists_all_verses(verses, fake_embedder, tmp_path):
    path = str(tmp_path / "chroma")
    count = build_index(verses, fake_embedder, path, "verses")
    assert count == len(verses)
    # 다시 열었을 때 영속되어 있어야 한다
    client = chromadb.PersistentClient(path)
    col = client.get_collection("verses")
    assert col.count() == len(verses)


def test_build_index_is_idempotent(verses, fake_embedder, tmp_path):
    path = str(tmp_path / "chroma")
    build_index(verses, fake_embedder, path, "verses")
    count = build_index(verses, fake_embedder, path, "verses")  # 재실행
    client = chromadb.PersistentClient(path)
    col = client.get_collection("verses")
    assert col.count() == len(verses)  # 중복 적재되지 않음
