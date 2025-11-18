SQL = """
SELECT
    id,
    content,
    1 - (embedding <=> %s::vector) AS sem_score
FROM chunks
WHERE workspace_id = %s
ORDER BY sem_score DESC
LIMIT 5;
"""
