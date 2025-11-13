from pydantic import BaseModel
from typing import List, Optional

class Citation(BaseModel):
    label: str
    stable_id: str = ""
    article_path: Optional[List[str]] = None

class QueryRequest(BaseModel):
    workspace_id: str
    question: str

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    usage: Optional[dict] = None

class IngestResponse(BaseModel):
    status: str
    ingested: int
    errors: int
    message: Optional[str] = None
