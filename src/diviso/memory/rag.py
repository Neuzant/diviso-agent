"""RAG over local files: chunking + TF-IDF search, index persisted in SQLite."""
from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

SUPPORTED = {".txt", ".md", ".py", ".json"}
_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return [c for c in chunks if c.strip()]


class RagIndex:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks (doc TEXT, idx INTEGER, text TEXT)")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_document(self, path: str | Path) -> int:
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)
        self.conn.execute("DELETE FROM chunks WHERE doc=?", (str(p),))
        self.conn.executemany("INSERT INTO chunks VALUES (?,?,?)",
                              [(str(p), i, c) for i, c in enumerate(chunks)])
        self.conn.commit()
        return len(chunks)

    def index_directory(self, root: str | Path) -> int:
        total = 0
        for p in sorted(Path(root).rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                total += self.add_document(p)
        return total

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        rows = self.conn.execute("SELECT doc, idx, text FROM chunks").fetchall()
        if not rows:
            return []
        docs_tokens = [tokenize(r[2]) for r in rows]
        n = len(rows)
        df: Counter = Counter()
        for toks in docs_tokens:
            df.update(set(toks))
        idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

        def vec(toks: list[str]) -> dict[str, float]:
            tf = Counter(toks)
            total = max(1, len(toks))
            return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}

        qv = vec(tokenize(query))
        scored = []
        for (doc, idx, text), toks in zip(rows, docs_tokens):
            dv = vec(toks)
            dot = sum(qv[t] * dv.get(t, 0.0) for t in qv)
            norm = math.sqrt(sum(v * v for v in dv.values())) * \
                math.sqrt(sum(v * v for v in qv.values()))
            score = dot / norm if norm else 0.0
            if score > 0:
                scored.append({"doc": doc, "chunk": idx, "text": text, "score": score})
        scored.sort(key=lambda r: -r["score"])
        return scored[:top_k]
