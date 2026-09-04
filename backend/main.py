import io
import os
import sys
import pandas as pd
from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware

# Ensure workspace root and backend directory are in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_current_dir, ".."))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from backend.config import settings
    from backend.models.schemas import UploadResponse, QueryRequest, QueryResponse
    from backend.profiler.schema_profiler import SchemaProfiler
    from backend.session.session_manager import session_manager
    from backend.agent.agent_builder import build_agent
    from backend.agent.self_correct import run_with_self_correction
except ImportError:
    from config import settings
    from models.schemas import UploadResponse, QueryRequest, QueryResponse
    from profiler.schema_profiler import SchemaProfiler
    from session.session_manager import session_manager
    from agent.agent_builder import build_agent
    from agent.self_correct import run_with_self_correction

app = FastAPI(
    title="Data Analysis Agent API",
    description="Natural language data analysis with sandboxed execution and self-correction.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "llm_provider": settings.llm_provider,
        "model_name": settings.model_name,
        "use_docker_sandbox": settings.use_docker_sandbox,
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not (filename.endswith(".csv") or filename.endswith((".xlsx", ".xls"))):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .csv, .xlsx, or .xls file.",
        )

    raw_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_mb} MB.",
        )

    try:
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(raw_bytes))
            except Exception:
                # Delimiter or encoding fallback
                df = pd.read_csv(io.BytesIO(raw_bytes), sep=None, engine="python", encoding="latin1")
        else:
            df = pd.read_excel(io.BytesIO(raw_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse spreadsheet: {type(e).__name__}: {e}",
        )

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded spreadsheet is empty.")

    profiler = SchemaProfiler(df)
    profile = profiler.profile()
    session_id = session_manager.create(df, profile)

    return UploadResponse(
        session_id=session_id,
        columns=profile["columns"],
        dtypes=profile["dtypes"],
        n_rows=profile["n_rows"],
        preview=profile["head"],
    )


@app.post("/query", response_model=QueryResponse)
async def query_dataset(req: QueryRequest):
    try:
        sess = session_manager.get(req.session_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Session not found or has expired. Please upload your dataset again.",
        )

    df = sess["df"]
    profile_str = SchemaProfiler(df).to_prompt_string()

    try:
        agent = build_agent(df, profile_str)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize data agent: {type(e).__name__}: {e}",
        )

    result = run_with_self_correction(agent, req.question, sess["history"])

    # Persist conversation turn
    session_manager.append_turn(req.session_id, "user", req.question)
    session_manager.append_turn(req.session_id, "assistant", result["answer"])

    return QueryResponse(
        answer=result["answer"],
        figure_json=result.get("figure_json"),
        code_run=result.get("code_run"),
        attempts=result.get("attempts", 1),
    )


@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    try:
        sess = session_manager.get(session_id)
        return {
            "session_id": session_id,
            "columns": sess["profile"]["columns"],
            "n_rows": sess["profile"]["n_rows"],
            "history_length": len(sess["history"]),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found or expired.")


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    deleted = session_manager.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": "Session deleted successfully."}
