import os
import pickle
import tempfile
from typing import Optional
import pandas as pd
from langchain_core.tools import tool
try:
    from backend.sandbox.executor import SandboxExecutor
    from backend.config import settings
except ImportError:
    from sandbox.executor import SandboxExecutor
    from config import settings


def make_execute_python_tool(
    df: pd.DataFrame,
    sandbox_timeout: int = 15,
    pickle_path: Optional[str] = None,
):
    """Creates a scoped execute_python LangChain tool for the given DataFrame."""
    if not pickle_path or not os.path.exists(pickle_path):
        tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
        pickle_path = tmp.name
        tmp.close()
        with open(pickle_path, "wb") as f:
            pickle.dump(df, f)

    executor = SandboxExecutor(timeout_s=sandbox_timeout)

    @tool
    def execute_python(code: str) -> dict:
        """Execute pandas/numpy/plotly code against the loaded DataFrame `df`.
        Assign your scalar or table output to `result` (e.g. `result = df['col'].mean()`),
        and optionally assign a Plotly figure to `fig` (e.g. `fig = px.bar(...)`).
        """
        return executor.run(code, pickle_path)

    return execute_python
