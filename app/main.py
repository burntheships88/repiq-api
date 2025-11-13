import os, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schema import QueryRequest, QueryResponse, Citation, IngestResponse
from .retriever import retrieve
from .db import ensure_schema, get_conn
from .embed import embed

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "supersecrettoken")
EMBED_DIM = int(os.getenv("EMBED_DIM", "3072"))

app = FastAPI(title="RepIQ RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    ensure_schema(EMBED_DIM)

SYSTEM_INSTRUCTIONS = (
    "You are RepIQ, an expert on the NFL/NFLPA CBA and incorporated policies. "
    "Answer ONLY from the provided context. If the answer is not clearly present, reply: "
    "\"Not determinable from the provided documents.\" "
    "Always include citations like [CBA → ARTICLE 13] or [Agent Regs → Section 3]."
)

def check_auth(request: Request):
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer ") or auth.split(" ",1)[1] != API_BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def call_llm(question: str, context: str) -> str:
    import requests
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-5",
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"}
            ]
        },
        timeout=90
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def build_context(rows, k=8):
    rows = rows[:k]
    blocks, cites = [], []
    for (row_id, document_id, article_path, text, *_) in rows:
        blocks.append(text.strip())
        label = " → ".join([p for p in (article_path or []) if p]) or str(document_id)
        cites.append({"label": label, "stable_id": "", "article_path": article_path})
    return "\n---\n".join(blocks), cites

@app.get("/")
def root():
    return {"ok": True, "name": "RepIQ RAG API", "version": "1.0.0"}

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    check_auth(request)
    rows = retrieve(req.workspace_id, req.question)
    if not rows:
        return QueryResponse(answer="Not determinable from the provided documents.", citations=[])
    context, cites = build_context(rows, k=8)
    answer = call_llm(req.question, context)
    return QueryResponse(answer=answer, citations=[Citation(**c) for c in cites])

@app.post("/admin/ingest", response_model=IngestResponse)
def admin_ingest(request: Request):
    check_auth(request)
    chunks_path = os.path.join(os.path.dirname(__file__), "..", "data", "chunks.jsonl")
    if not os.path.exists(chunks_path):
        raise HTTPException(status_code=500, detail="chunks.jsonl not found in /data")
    ingested, errors = 0, 0
    workspace_name = os.getenv("WORKSPACE_NAME", "NFLPA-Prod")
    try:
        with get_conn() as conn, conn.cursor() as cur, open(chunks_path, "r", encoding="utf-8") as f:
            cur.execute("SELECT id FROM workspaces WHERE name=%s", (workspace_name,))
            row = cur.fetchone()
            if row: ws_id = row[0]
            else:
                cur.execute("INSERT INTO workspaces (name) VALUES (%s) RETURNING id", (workspace_name,))
                ws_id = cur.fetchone()[0]
            docs = {}
            for line in f:
                try:
                    rec = json.loads(line)
                    doc_id = rec["doc_id"]
                    if doc_id not in docs:
                        cur.execute("""
                          INSERT INTO documents (workspace_id, doc_id, title, version)
                          VALUES (%s,%s,%s,%s)
                          ON CONFLICT (workspace_id, doc_id) DO UPDATE
                          SET title=EXCLUDED.title, version=EXCLUDED.version
                          RETURNING id
                        """, (ws_id, doc_id, rec.get("title",""), rec.get("version","")))
                        docs[doc_id] = cur.fetchone()[0]
                    vec = embed(rec["text"])
                    cur.execute("""
                      INSERT INTO chunks
                        (workspace_id, document_id, stable_id, article_path, char_start, char_end, text, embedding)
                      VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s)
                      ON CONFLICT (workspace_id, stable_id) DO NOTHING
                    """, (
                        ws_id, docs[doc_id], rec.get("stable_id",""), rec.get("article_path"),
                        (rec.get("char_range") or [None, None])[0],
                        (rec.get("char_range") or [None, None])[1],
                        rec.get("text",""), vec
                    ))
                    ingested += 1
                except Exception as e:
                    errors += 1
            conn.commit()
        return IngestResponse(status="ok", ingested=ingested, errors=errors, message="Workspace name: NFLPA-Prod (look up its UUID in DB).")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
