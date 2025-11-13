import os, psycopg
from contextlib import contextmanager

def _dsn():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db   = os.getenv("PGDATABASE", "repiq")
    user = os.getenv("PGUSER", "repiq")
    pwd  = os.getenv("PGPASSWORD", "repiqpassword")
    return f"host={host} port={port} dbname={db} user={user} password={pwd}"

@contextmanager
def get_conn():
    with psycopg.connect(_dsn()) as conn:
        yield conn

def ensure_schema(embed_dim: int = 3072):
    SQL = f"""
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS workspaces (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      name text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
      doc_id text NOT NULL,
      title text NOT NULL,
      version text,
      source_url text,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id, doc_id)
    );
    CREATE TABLE IF NOT EXISTS chunks (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
      document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      stable_id text NOT NULL,
      article_path text[],
      char_start int,
      char_end int,
      text text NOT NULL,
      text_tsv tsvector,
      embedding vector({embed_dim}),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id, stable_id)
    );
    CREATE OR REPLACE FUNCTION chunks_tsv_update() RETURNS trigger AS $$
    BEGIN
      NEW.text_tsv := to_tsvector('english', coalesce(NEW.text,''));
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_chunks_tsv ON chunks;
    CREATE TRIGGER trg_chunks_tsv
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update();

    CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (text_tsv);
    CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id);
    CREATE INDEX IF NOT EXISTS chunks_ws_idx  ON chunks (workspace_id);
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        conn.commit()
