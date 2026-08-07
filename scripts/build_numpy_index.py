"""오프라인 인덱스 빌드: JSONL -> numpy 벡터 인덱스 (경량 배포용, chromadb 불필요)."""
from pathlib import Path

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.factory import _make_embedder
from bible_search.vectorstore import build_numpy_index


def main() -> None:
    s = get_settings()
    verses = load_verses(s.data_path)
    print(f"loaded {len(verses)} verses from {s.data_path}")

    embedder = _make_embedder(s)
    print(f"target dim: {s.numpy_index_dim if s.numpy_index_dim is not None else 'full (no reduction)'}")
    count = build_numpy_index(verses, embedder, s.numpy_index_path, dim=s.numpy_index_dim)
    print(f"indexed {count} verses into {s.numpy_index_path}")

    out_path = Path(s.numpy_index_path)
    basis_written = (out_path / "basis.npy").exists()
    print(f"basis written: {basis_written}")
    for name in ("vectors.npy", "ids.json", "basis.npy"):
        f = out_path / name
        if f.exists():
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  {name}: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
