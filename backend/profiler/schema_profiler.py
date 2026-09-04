import math
from typing import Any
import pandas as pd


class SchemaProfiler:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def profile(self) -> dict[str, Any]:
        # Handle empty dataframe edge-case
        n_rows = len(self.df)
        n_cols = len(self.df.columns)

        # Replace NaN with None for clean JSON serialization
        preview_df = self.df.head(5).copy()
        preview_records = preview_df.where(pd.notnull(preview_df), None).to_dict(orient="records")

        null_pct = {}
        for c in self.df.columns:
            pct = (self.df[c].isna().mean() * 100) if n_rows > 0 else 0.0
            null_pct[c] = round(float(pct), 1)

        prof: dict[str, Any] = {
            "columns": [str(c) for c in self.df.columns],
            "dtypes": {str(c): str(t) for c, t in self.df.dtypes.items()},
            "n_rows": n_rows,
            "n_cols": n_cols,
            "null_pct": null_pct,
            "head": preview_records,
            "numeric_stats": {},
            "categorical_stats": {},
        }

        # Numeric stats
        numeric_cols = self.df.select_dtypes(include="number").columns
        for c in numeric_cols:
            series = self.df[c].dropna()
            if not series.empty:
                min_val = float(series.min())
                max_val = float(series.max())
                mean_val = float(series.mean())
                prof["numeric_stats"][str(c)] = {
                    "min": None if math.isnan(min_val) else round(min_val, 3),
                    "max": None if math.isnan(max_val) else round(max_val, 3),
                    "mean": None if math.isnan(mean_val) else round(mean_val, 3),
                }

        # Categorical / Object stats
        cat_cols = self.df.select_dtypes(include=["object", "category", "string"]).columns
        for c in cat_cols:
            series = self.df[c].dropna()
            if not series.empty:
                top_counts = series.value_counts().head(5).to_dict()
                prof["categorical_stats"][str(c)] = {str(k): int(v) for k, v in top_counts.items()}

        return prof

    def to_prompt_string(self) -> str:
        p = self.profile()
        lines = [f"Dataset Shape: {p['n_rows']} rows x {p['n_cols']} columns", "Columns:"]
        for c in p["columns"]:
            dtype = p["dtypes"].get(c, "unknown")
            nulls = p["null_pct"].get(c, 0.0)
            col_info = f"- `{c}` ({dtype}, {nulls}% null)"

            if c in p.get("numeric_stats", {}):
                stats = p["numeric_stats"][c]
                col_info += f" | min={stats['min']}, max={stats['max']}, mean={stats['mean']}"
            elif c in p.get("categorical_stats", {}):
                cats = p["categorical_stats"][c]
                top_items = [f"{k}: {v}" for k, v in list(cats.items())[:3]]
                if top_items:
                    col_info += f" | top values: [{', '.join(top_items)}]"

            lines.append(col_info)

        lines.append("\nSample rows (first 5):")
        for i, row in enumerate(p["head"], 1):
            lines.append(f"{i}. {row}")

        return "\n".join(lines)
