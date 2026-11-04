"""SQLite persistence and scoped document storage. Only caller-selected session data is returned."""
from __future__ import annotations
import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PAGES = 60
MAX_PAGE_CHARS = 12000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_db_path() -> str:
    return os.environ.get("DOCPILOT_DB", str(Path(__file__).resolve().parents[1] / "runtime" / "docpilot.sqlite3"))


class Storage:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or default_db_path())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connection(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _init(self):
        with self.connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                kind TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner);
            CREATE TABLE IF NOT EXISTS pages (
                document_id TEXT NOT NULL, page_no INTEGER NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY(document_id, page_no),
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS memories (
                owner TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(owner, key)
            );
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                owner TEXT NOT NULL, run_id TEXT NOT NULL,
                action TEXT NOT NULL, tool TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                owner TEXT NOT NULL, run_id TEXT NOT NULL, model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                cached_tokens INTEGER NOT NULL, estimated_cost_usd REAL NOT NULL
            );
            """)

    def add_document(self, owner: str, title: str, body: bytes) -> dict:
        if not isinstance(body, bytes) or len(body) == 0 or len(body) > MAX_UPLOAD_BYTES:
            raise ValueError("Document is empty or exceeds the 8 MB upload limit")
        filename = Path(title).name[:120]
        extension = Path(filename).suffix.lower()
        if extension not in {".txt", ".md", ".pdf"}:
            raise ValueError("Only .txt, .md and .pdf documents are accepted")
        if extension == ".pdf":
            from io import BytesIO
            from pypdf import PdfReader
            try:
                reader = PdfReader(BytesIO(body), strict=False)
                if reader.is_encrypted:
                    raise ValueError("Password-protected PDF files are not supported")
                if len(reader.pages) > MAX_PAGES:
                    raise ValueError("PDF exceeds the 60-page cap")
                pages = [(page.extract_text() or "")[:MAX_PAGE_CHARS] for page in reader.pages]
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("Could not extract text from this PDF") from exc
        else:
            text = body.decode("utf-8", errors="replace")
            text = text[:MAX_PAGES * MAX_PAGE_CHARS]
            pages = [text[i:i + 3000] for i in range(0, len(text), 3000)] or [""]
        if not any(page.strip() for page in pages):
            raise ValueError("No extractable text: OCR/scanned-only PDFs are not supported")
        doc_id = str(uuid.uuid4())
        digest = hashlib.sha256(body).hexdigest()
        with self.connection() as conn:
            conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)", (doc_id, owner, filename, extension, digest, utc_now()))
            conn.executemany("INSERT INTO pages VALUES (?,?,?)", [(doc_id, i + 1, text) for i, text in enumerate(pages)])
        return {"id": doc_id, "title": filename, "page_count": len(pages), "sha256": digest}

    def list_documents(self, owner: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute("""SELECT d.id, d.title, d.kind, d.sha256, d.created_at, COUNT(p.page_no) AS page_count
                FROM documents d JOIN pages p ON p.document_id=d.id
                WHERE d.owner=? GROUP BY d.id ORDER BY d.created_at DESC""", (owner,)).fetchall()
            return [dict(r) for r in rows]

    def delete_document(self, owner: str, document_id: str) -> bool:
        """Delete only the current owner's document and its indexed pages."""
        with self.connection() as conn:
            result = conn.execute("DELETE FROM documents WHERE owner=? AND id=?", (owner, document_id))
            return result.rowcount > 0

    def get_pages(self, owner: str, doc_id: str | None = None) -> list[dict]:
        query = """SELECT d.id AS document_id, d.title, p.page_no, p.body
            FROM documents d JOIN pages p ON d.id=p.document_id WHERE d.owner=?"""
        params = [owner]
        if doc_id is not None:
            query += " AND d.id=?"
            params.append(doc_id)
        query += " ORDER BY d.title, p.page_no"
        with self.connection() as conn:
            return [dict(x) for x in conn.execute(query, params).fetchall()]

    def recall_memory(self, owner: str, key: str) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT key, value, updated_at FROM memories WHERE owner=? AND key=?", (owner, key)).fetchone()
        return dict(row) if row else {"found": False, "key": key}

    def save_memory(self, owner: str, key: str, value: str) -> dict:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", key) or len(value) > 400:
            raise ValueError("Memory key or value violates validation constraints")
        with self.connection() as conn:
            conn.execute("""INSERT INTO memories (owner,key,value,updated_at) VALUES (?,?,?,?)
                ON CONFLICT(owner,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (owner, key, value, utc_now()))
        return {"saved": True, "key": key}

    def list_memories(self, owner: str) -> list[dict]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM memories WHERE owner=? ORDER BY key", (owner,)).fetchall()]

    def save_report(self, owner: str, title: str, body: str) -> dict:
        if not title.strip() or len(title) > 100 or not body.strip() or len(body) > 6000:
            raise ValueError("Report title/body exceed validation constraints")
        report_id = str(uuid.uuid4())
        with self.connection() as conn:
            conn.execute("INSERT INTO reports VALUES (?,?,?,?,?)", (report_id, owner, title, body, utc_now()))
        return {"saved": True, "report_id": report_id, "title": title}

    def list_reports(self, owner: str) -> list[dict]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM reports WHERE owner=? ORDER BY created_at DESC", (owner,)).fetchall()]

    def audit(self, owner: str, run_id: str, action: str, tool: str, outcome: str, detail: str = ""):
        with self.connection() as conn:
            conn.execute("INSERT INTO audit (occurred_at,owner,run_id,action,tool,outcome,detail) VALUES (?,?,?,?,?,?,?)",
                         (utc_now(), owner, run_id, action, tool, outcome, detail[:300]))

    def audits(self, owner: str, limit: int = 100) -> list[dict]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM audit WHERE owner=? ORDER BY id DESC LIMIT ?", (owner, min(limit, 500))).fetchall()]

    def record_usage(self, owner: str, run_id: str, model: str, in_tok: int, out_tok: int, cached: int, amount: float):
        with self.connection() as conn:
            conn.execute("""INSERT INTO usage (occurred_at,owner,run_id,model,input_tokens,output_tokens,cached_tokens,estimated_cost_usd)
                         VALUES (?,?,?,?,?,?,?,?)""", (utc_now(), owner, run_id, model, in_tok, out_tok, cached, amount))

    def usage_summary(self, owner: str) -> dict:
        with self.connection() as conn:
            row = conn.execute("""SELECT COUNT(DISTINCT run_id) as runs, COALESCE(SUM(input_tokens),0) as input_tokens,
              COALESCE(SUM(output_tokens),0) as output_tokens,
              COALESCE(SUM(estimated_cost_usd),0) as estimated_total_usd
              FROM usage WHERE owner=?""", (owner,)).fetchone()
        return dict(row)