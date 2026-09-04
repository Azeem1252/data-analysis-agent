import numpy as np
import pandas as pd
import pytest
from backend.profiler.schema_profiler import SchemaProfiler


@pytest.fixture
def fixture_dataframe():
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", None],
        "age": [25, 30, np.nan, 40, 50],
        "salary": [50000.0, 60000.0, 75000.0, 80000.0, 95000.0],
        "department": ["Engineering", "Sales", "Engineering", "Marketing", "Sales"],
    })


def test_profiler_null_math(fixture_dataframe):
    profiler = SchemaProfiler(fixture_dataframe)
    prof = profiler.profile()

    assert prof["n_rows"] == 5
    assert prof["n_cols"] == 4
    # 1 null out of 5 = 20.0%
    assert prof["null_pct"]["name"] == 20.0
    assert prof["null_pct"]["age"] == 20.0
    assert prof["null_pct"]["salary"] == 0.0


def test_profiler_numeric_stats(fixture_dataframe):
    profiler = SchemaProfiler(fixture_dataframe)
    prof = profiler.profile()

    assert "salary" in prof["numeric_stats"]
    assert prof["numeric_stats"]["salary"]["min"] == 50000.0
    assert prof["numeric_stats"]["salary"]["max"] == 95000.0
    assert prof["numeric_stats"]["salary"]["mean"] == 72000.0


def test_profiler_categorical_stats(fixture_dataframe):
    profiler = SchemaProfiler(fixture_dataframe)
    prof = profiler.profile()

    assert "department" in prof["categorical_stats"]
    assert prof["categorical_stats"]["department"]["Engineering"] == 2
    assert prof["categorical_stats"]["department"]["Sales"] == 2


def test_profiler_to_prompt_string(fixture_dataframe):
    profiler = SchemaProfiler(fixture_dataframe)
    prompt_str = profiler.to_prompt_string()

    assert "5 rows x 4 columns" in prompt_str
    assert "salary" in prompt_str
    assert "department" in prompt_str
    assert "Sample rows" in prompt_str
    # Length bounded: should not contain excessive text
    assert len(prompt_str) < 3000


def test_profiler_empty_dataframe():
    empty_df = pd.DataFrame(columns=["a", "b", "c"])
    profiler = SchemaProfiler(empty_df)
    prof = profiler.profile()

    assert prof["n_rows"] == 0
    assert prof["n_cols"] == 3
    assert prof["null_pct"]["a"] == 0.0
