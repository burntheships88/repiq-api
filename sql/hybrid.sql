-- app/sql/hybrid.sql
-- Hybrid semantic search query used by retriever.py

SELECT
  id,
  content,
  1 - (embedding <-> %(qvec)s) AS sem_score
FROM chunks
WHERE workspace_id = %(ws)s
ORDER BY sem_score DESC
LIMIT 8;
