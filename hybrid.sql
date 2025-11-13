WITH
sem AS (
  SELECT id, document_id, article_path, text,
         1 - (embedding <=> :qvec) AS sem_score
  FROM chunks
  WHERE workspace_id = :ws
  ORDER BY embedding <=> :qvec
  LIMIT 30
),
lex AS (
  SELECT id, document_id, article_path, text,
         ts_rank_cd(text_tsv, plainto_tsquery('english', :qtext)) AS lex_score
  FROM chunks
  WHERE workspace_id = :ws
    AND text_tsv @@ plainto_tsquery('english', :qtext)
  ORDER BY lex_score DESC
  LIMIT 30
),
unioned AS (
  SELECT id, document_id, article_path, text, sem_score, NULL::float AS lex_score FROM sem
  UNION
  SELECT id, document_id, article_path, text, NULL::float AS sem_score, lex_score FROM lex
)
SELECT id, document_id, article_path, text,
       COALESCE(sem_score,0) AS sem_score,
       COALESCE(lex_score,0) AS lex_score,
       COALESCE(sem_score,0) + 0.6*COALESCE(lex_score,0) AS score
FROM unioned
GROUP BY id, document_id, article_path, text, sem_score, lex_score
ORDER BY score DESC
LIMIT 30;
