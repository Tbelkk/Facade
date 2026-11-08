"""Shared paths so every module agrees on where things live."""
from pathlib import Path

INGEST_DIR = Path(__file__).resolve().parent
CORE_DIR = INGEST_DIR.parent
REPO_ROOT = CORE_DIR.parent
PROMPTS_DIR = REPO_ROOT / "shared" / "prompts"
FIXTURES_DIR = REPO_ROOT / "shared" / "fixtures"
CACHE_DIR = CORE_DIR / "cache"


def resolve(path_str, *bases):
    """Find a file given as absolute, relative to cwd, or relative to any base folder."""
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_file():
        return p.resolve()
    for base in bases:
        if base is None:
            continue
        cand = Path(base) / path_str
        if cand.is_file():
            return cand.resolve()
    cand = REPO_ROOT / path_str
    return cand.resolve() if cand.is_file() else None
