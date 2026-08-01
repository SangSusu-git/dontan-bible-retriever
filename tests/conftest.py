from pathlib import Path
import pytest
from bible_search.data.loader import load_verses

FIXTURE = Path(__file__).parent / "data" / "verses_fixture.jsonl"

@pytest.fixture
def verses():
    return load_verses(FIXTURE)
