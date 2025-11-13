import os
from typing import List, Tuple
from .db import get_conn
from .embed import embed

SQL = None
with open(os.path.join(os.path.dirname(__file__), "..", "sql", "hybrid.sql")) as f:
    SQL = f.read()

def retrieve(workspace_id: str, question: str) -> List[Tuple]:
    qvec = embed(question)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL, {"ws": workspace_id, "qvec": qvec, "qtext": question})
            return cur.fetchall()
