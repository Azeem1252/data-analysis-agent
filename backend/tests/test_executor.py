import os
import pickle
import tempfile
import pandas as pd
import pytest
from backend.sandbox.executor import SandboxExecutor


@pytest.fixture
def sample_df_pickle():
    df = pd.DataFrame({
        "category": ["A", "B", "A", "B", "C"],
        "sales": [100, 200, 150, 250, 300],
        "quantity": [1, 2, 1, 3, 4],
    })
    tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
    tmp_path = tmp.name
    tmp.close()

    with open(tmp_path, "wb") as f:
        pickle.dump(df, f)

    yield tmp_path

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def test_executor_happy_path(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=10)
    code = "result = df['sales'].mean()"
    out = executor.run(code, sample_df_pickle)

    assert out["success"] is True
    assert out["result_repr"] is not None
    assert "200.0" in out["result_repr"] or "200" in out["result_repr"]
    assert out["error"] is None


def test_executor_dataframe_result(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=10)
    code = "result = df.groupby('category')['sales'].sum()"
    out = executor.run(code, sample_df_pickle)

    assert out["success"] is True
    assert "category" in out["result_repr"]
    assert "sales" in out["result_repr"] or "250" in out["result_repr"]


def test_executor_blocked_imports(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=10)

    # Test import os
    out1 = executor.run("import os\nresult = os.getcwd()", sample_df_pickle)
    assert out1["success"] is False
    assert "Security Alert" in out1["error"] or "not permitted" in out1["error"]

    # Test import subprocess
    out2 = executor.run("import subprocess\nresult = 1", sample_df_pickle)
    assert out2["success"] is False
    assert "Security Alert" in out2["error"] or "not permitted" in out2["error"]

    # Test from socket import socket
    out3 = executor.run("from socket import socket\nresult = 1", sample_df_pickle)
    assert out3["success"] is False
    assert "Security Alert" in out3["error"] or "not permitted" in out3["error"]


def test_executor_chart_generation(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=10)
    code = "fig = px.bar(df, x='category', y='sales', title='Sales by Category')\nresult = 'Chart created'"
    out = executor.run(code, sample_df_pickle)

    assert out["success"] is True
    assert out["figure_json"] is not None
    assert "Sales by Category" in out["figure_json"]
    assert "bar" in out["figure_json"]


def test_executor_runtime_error(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=10)
    code = "result = df['non_existent_column'] + 1"
    out = executor.run(code, sample_df_pickle)

    assert out["success"] is False
    assert out["error"] is not None
    assert "KeyError" in out["error"]


def test_executor_timeout(sample_df_pickle):
    executor = SandboxExecutor(timeout_s=2)
    code = "while True:\n    pass"
    out = executor.run(code, sample_df_pickle)

    assert out["success"] is False
    assert out["error"] is not None
    assert "timed out" in out["error"].lower()
