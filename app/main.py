from pathlib import Path
import re
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from .config import UPLOAD_DIR, MAX_UPLOAD_MB, ADMIN_API_KEY
from .db import init_db, db
from .processing import clean_text, detect_language, extract_file, digest
from .collector import crawl_site

app = FastAPI(title="Vytron Data Engine", version="0.1.0")

def require_key(x_api_key: str | None = Header(default=None)):
    if ADMIN_API_KEY and x_api_key != ADMIN_API_KEY:
        raise HTTPException(401, "Invalid or missing API key")

@app.on_event("startup")
def startup():
    init_db()

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status":"ok","service":"Vytron Data Engine","version":"0.1.0"}

@app.get("/api/stats", dependencies=[Depends(require_key)])
def stats():
    with db() as con:
        q = lambda sql: con.execute(sql).fetchone()[0]
        return {"documents":q("SELECT COUNT(*) FROM documents"),
                "approved":q("SELECT COUNT(*) FROM documents WHERE status='approved'"),
                "pending":q("SELECT COUNT(*) FROM documents WHERE status='pending'"),
                "shona":q("SELECT COUNT(*) FROM documents WHERE language IN ('sn','sn-review')"),
                "crawl_jobs":q("SELECT COUNT(*) FROM crawl_jobs")}

@app.get("/api/documents", dependencies=[Depends(require_key)])
def documents(status: str | None = None, limit: int = 100):
    limit = max(1,min(limit,500))
    with db() as con:
        if status in ("pending","approved","rejected"):
            rows = con.execute("SELECT id,title,source,source_type,language,status,created_at FROM documents WHERE status=? ORDER BY id DESC LIMIT ?",(status,limit)).fetchall()
        else:
            rows = con.execute("SELECT id,title,source,source_type,language,status,created_at FROM documents ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    return [dict(x) for x in rows]

@app.get("/api/documents/{doc_id}", dependencies=[Depends(require_key)])
def document_detail(doc_id: int):
    with db() as con:
        row = con.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone()
    if not row: raise HTTPException(404,"Document not found")
    item = dict(row); item["content"] = item["content"][:12000]
    return item

@app.post("/api/upload", dependencies=[Depends(require_key)])
async def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "upload").name
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf",".epub",".txt"):
        raise HTTPException(400,"Upload PDF, EPUB or TXT only")
    raw = await file.read(MAX_UPLOAD_MB*1024*1024+1)
    if len(raw) > MAX_UPLOAD_MB*1024*1024:
        raise HTTPException(413,f"Maximum upload size is {MAX_UPLOAD_MB} MB")
    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
    path = UPLOAD_DIR / name
    if path.exists(): path = UPLOAD_DIR / f"{path.stem}_{digest(name+str(len(raw)))[:8]}{suffix}"
    path.write_bytes(raw)
    try:
        text = clean_text(extract_file(path))
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400,f"Could not extract text: {e}")
    if len(text) < 40: raise HTTPException(400,"No usable text found; scanned PDFs need OCR.")
    try:
        with db() as con:
            cur = con.execute("""INSERT INTO documents(title,source,source_type,language,content,status,content_hash)
                VALUES(?,?,?,?,?,'pending',?)""",(Path(name).stem,f"upload:{name}","file",detect_language(text),text,digest(text)))
            doc_id = cur.lastrowid
    except Exception as e:
        if "UNIQUE" in str(e): raise HTTPException(409,"This document is already in the library.")
        raise
    return {"id":doc_id,"title":Path(name).stem,"language":detect_language(text),"status":"pending","characters":len(text)}

class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 5

@app.post("/api/crawl", dependencies=[Depends(require_key)])
async def crawl(req: CrawlRequest):
    try:
        result = await crawl_site(str(req.url),req.max_pages)
        with db() as con:
            con.execute("INSERT INTO crawl_jobs(url,status,pages_found,pages_saved,message) VALUES(?,?,?,?,?)",
                        (str(req.url),"completed",result["pages_found"],result["pages_saved"],"Items await review"))
        return {"status":"completed",**result}
    except Exception as e:
        with db() as con:
            con.execute("INSERT INTO crawl_jobs(url,status,message) VALUES(?,?,?)",(str(req.url),"failed",str(e)[:500]))
        raise HTTPException(400,str(e))

@app.post("/api/documents/{doc_id}/approve", dependencies=[Depends(require_key)])
def approve(doc_id: int):
    with db() as con:
        cur = con.execute("UPDATE documents SET status='approved',approved_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'",(doc_id,))
        if not cur.rowcount: raise HTTPException(404,"Pending document not found")
    return {"id":doc_id,"status":"approved"}

@app.post("/api/documents/{doc_id}/reject", dependencies=[Depends(require_key)])
def reject(doc_id: int):
    with db() as con:
        cur = con.execute("UPDATE documents SET status='rejected' WHERE id=? AND status='pending'",(doc_id,))
        if not cur.rowcount: raise HTTPException(404,"Pending document not found")
    return {"id":doc_id,"status":"rejected"}

@app.delete("/api/documents/{doc_id}", dependencies=[Depends(require_key)])
def delete(doc_id: int):
    with db() as con:
        cur = con.execute("DELETE FROM documents WHERE id=?",(doc_id,))
        if not cur.rowcount: raise HTTPException(404,"Document not found")
    return {"deleted":doc_id}

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

@app.post("/api/search", dependencies=[Depends(require_key)])
def search(req: SearchRequest):
    terms = re.findall(r"[\w'-]+",req.query.strip())
    if not terms: return {"query":req.query,"results":[]}
    match = " OR ".join('"'+t.replace('"','""')+'"' for t in terms[:12])
    with db() as con:
        rows = con.execute("""SELECT d.id,d.title,d.source,d.language,
            snippet(documents_fts,1,'[',']','…',18) AS excerpt
            FROM documents_fts JOIN documents d ON d.id=documents_fts.rowid
            WHERE documents_fts MATCH ? AND d.status='approved' ORDER BY rank LIMIT ?""",
            (match,max(1,min(req.limit,10)))).fetchall()
    return {"query":req.query,"results":[dict(x) for x in rows]}

@app.get("/api/jobs", dependencies=[Depends(require_key)])
def jobs():
    with db() as con:
        rows = con.execute("SELECT * FROM crawl_jobs ORDER BY id DESC LIMIT 30").fetchall()
    return [dict(x) for x in rows]
