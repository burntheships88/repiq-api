import os
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

# DATABASE_URL should already be set in your Render Environment
DATABASE_URL = os.environ["DATABASE_URL"]


def retrieve(workspace_id: str, qvec: List[float], question: str) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval (semantic + keyword) from the chunks table.

    - workspace_id: UUID of the workspace as a string
    - qvec: embedding vector for the question (length 1536 for text-embedding-3-small)
    - question: the raw question text (used for keyword search)
    """

    # IMPORTANT: cast %(qvec)s to ::vector so it matches embedding::vector
    sql = """
    WITH ranked AS (
        SELECT
            id,
            content,
            1 - (embedding <=> %(qvec)s::vector) AS sem_score,
            ts_rank(chunks_tsv, plainto_tsquery('english', %(qtext)s)) AS lex_score
        FROM chunks
        WHERE workspace_id = %(ws)s
        ORDER BY sem_score DESC
        LIMIT 50
    )
    SELECT
        id,
        content,
        sem_score,
        lex_score,
        sem_score + lex_score AS total_score
    FROM ranked
    ORDER BY total_score DESC
    LIMIT 5;
    """

    # psycopg2 will send qvec as a double precision[]; the ::vector cast on the SQL
    # side fixes the earlier "vector <-> double precision[]" error.
    params = {
        "ws": workspace_id,
        "qvec": qvec,
        "qtext": question,
    }

    with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    # rows is already a list of dicts because of RealDictCursor
    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": str(row["id"]),
                "content": row["content"],
                "sem_score": float(row["sem_score"]),
                "lex_score": float(row["lex_score"]),
                "score": float(row["total_score"]),
            }
        )

    return results
