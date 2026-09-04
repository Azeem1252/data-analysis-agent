from typing import Optional, Any
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    session_id: str
    columns: list[str]
    dtypes: dict[str, str]
    n_rows: int
    preview: list[dict[str, Any]]


class QueryRequest(BaseModel):
    session_id: str
    question: str


class ExecResult(BaseModel):
    success: bool
    stdout: str = ""
    result_repr: Optional[str] = None
    figure_json: Optional[str] = None  # Plotly fig.to_json()
    error: Optional[str] = None
    code_run: str = ""


class QueryResponse(BaseModel):
    answer: str
    figure_json: Optional[str] = None
    code_run: Optional[str] = None
    attempts: int
