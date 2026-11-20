import sqlite3
from contextlib import contextmanager
from .config import DB_PATH, UPLOAD_DIR

@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS documents(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL, source TEXT NOT NULL, source_type TEXT NOT NULL,
          language TEXT NOT NULL DEFAULT 'unknown', content TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', content_hash TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          approved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS crawl_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, status TEXT NOT NULL,
          pages_found INTEGER DEFAULT 0, pages_saved INTEGER DEFAULT 0,
          message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title,content,content='documents',content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
          INSERT INTO documents_fts(rowid,title,content) VALUES(new.id,new.title,new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
          INSERT INTO documents_fts(documents_fts,rowid,title,content) VALUES('delete',old.id,old.title,old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
          INSERT INTO documents_fts(documents_fts,rowid,title,content) VALUES('delete',old.id,old.title,old.content);
          INSERT INTO documents_fts(rowid,title,content) VALUES(new.id,new.title,new.content);
        END;
        """)
