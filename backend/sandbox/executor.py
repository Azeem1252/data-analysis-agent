import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from typing import Any, Optional
try:
    from backend.config import settings
except ImportError:
    from config import settings

BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
    "http", "ftplib", "builtins", "importlib", "pathlib", "pty", "commands",
    "posix", "threading", "multiprocessing", "ctypes", "signal"
}

BLOCKED_PATTERNS = [
    r"__import__",
    r"__builtins__",
    r"open\s*\(",
    r"exec\s*\(",
    r"eval\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"globals\s*\(",
    r"locals\s*\(",
]


class SandboxExecutor:
    def __init__(self, timeout_s: Optional[int] = None):
        self.timeout_s = timeout_s or settings.sandbox_timeout_seconds

    def _static_check(self, code: str) -> None:
        # Check blocked module imports
        for bad in BLOCKED_IMPORTS:
            pattern = rf"(?:^|\n)\s*(?:import\s+{bad}|from\s+{bad})"
            if re.search(pattern, code):
                raise ValueError(f"Security Alert: Use of module '{bad}' is not permitted in the sandbox.")

        # Check dangerous builtin invocations
        for pat in BLOCKED_PATTERNS:
            if re.search(pat, code):
                raise ValueError(f"Security Alert: Blocked pattern '{pat}' detected in execution code.")

    def run(self, code: str, df_pickle_path: str) -> dict[str, Any]:
        try:
            self._static_check(code)
        except ValueError as e:
            return {
                "success": False,
                "stdout": "",
                "result_repr": None,
                "figure_json": None,
                "error": str(e),
                "code_run": code,
            }

        if settings.use_docker_sandbox:
            return self._run_docker(code, df_pickle_path)
        return self._run_subprocess(code, df_pickle_path)

    def _run_subprocess(self, code: str, df_pickle_path: str) -> dict[str, Any]:
        escaped_path = df_pickle_path.replace("\\", "\\\\")

        runner_script = textwrap.dedent(f"""
            import sys, json, pickle, io
            from contextlib import redirect_stdout, redirect_stderr

            # Cross-platform resource limits
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_CPU, ({self.timeout_s}, {self.timeout_s}))
            except Exception:
                pass

            import pandas as pd
            import numpy as np
            import plotly.express as px
            import plotly.graph_objects as go

            with open("{escaped_path}", "rb") as f:
                df = pickle.load(f)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            ns = {{
                "pd": pd,
                "np": np,
                "px": px,
                "go": go,
                "df": df,
                "result": None,
                "fig": None,
            }}

            success = False
            error = None
            fig_json = None
            result_repr = None

            try:
                compiled = compile({code!r}, "<agent_code>", "exec")
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(compiled, ns)

                success = True
                res = ns.get("result")
                if res is not None:
                    if isinstance(res, (pd.DataFrame, pd.Series)):
                        result_repr = str(res)
                    else:
                        result_repr = repr(res)

                fig = ns.get("fig")
                if fig is not None and hasattr(fig, "to_json"):
                    fig_json = fig.to_json()

            except Exception as e:
                success = False
                error = f"{{type(e).__name__}}: {{e}}"

            out = {{
                "success": success,
                "stdout": stdout_capture.getvalue(),
                "result_repr": result_repr,
                "figure_json": fig_json,
                "error": error,
            }}
            print("___SANDBOX_OUTPUT_START___")
            print(json.dumps(out))
            print("___SANDBOX_OUTPUT_END___")
        """)

        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", runner_script],
                capture_output=True,
                text=True,
                timeout=self.timeout_s + 2,
            )

            stdout = proc.stdout
            if "___SANDBOX_OUTPUT_START___" in stdout:
                payload = stdout.split("___SANDBOX_OUTPUT_START___")[1].split("___SANDBOX_OUTPUT_END___")[0].strip()
                res = json.loads(payload)
                res["code_run"] = code
                return res

            # Fallback parsing
            lines = [l for l in stdout.strip().splitlines() if l.startswith("{") and l.endswith("}")]
            if lines:
                res = json.loads(lines[-1])
                res["code_run"] = code
                return res

            err_msg = proc.stderr.strip() or "Sandbox produced no output."
            return {
                "success": False,
                "stdout": stdout,
                "result_repr": None,
                "figure_json": None,
                "error": err_msg,
                "code_run": code,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "result_repr": None,
                "figure_json": None,
                "error": f"Execution timed out after {self.timeout_s} seconds.",
                "code_run": code,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "result_repr": None,
                "figure_json": None,
                "error": f"Sandbox execution error: {type(e).__name__}: {e}",
                "code_run": code,
            }

    def _run_docker(self, code: str, df_pickle_path: str) -> dict[str, Any]:
        """Docker sandbox runner for isolated execution."""
        temp_dir = tempfile.mkdtemp(prefix="sandbox_docker_")
        run_script_path = os.path.join(temp_dir, "run.py")
        pickle_dst = os.path.join(temp_dir, "data.pkl")

        try:
            # Copy dataframe pickle to temp mount
            import shutil
            shutil.copyfile(df_pickle_path, pickle_dst)

            runner_code = textwrap.dedent(f"""
                import json, pickle, io, sys
                from contextlib import redirect_stdout, redirect_stderr
                import pandas as pd, numpy as np
                import plotly.express as px, plotly.graph_objects as go

                with open("/data/data.pkl", "rb") as f:
                    df = pickle.load(f)

                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                ns = {{"pd": pd, "np": np, "px": px, "go": go, "df": df, "result": None, "fig": None}}

                success, error, fig_json, result_repr = False, None, None, None
                try:
                    compiled = compile({code!r}, "<agent_code>", "exec")
                    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                        exec(compiled, ns)
                    success = True
                    res = ns.get("result")
                    if res is not None:
                        result_repr = str(res) if isinstance(res, (pd.DataFrame, pd.Series)) else repr(res)
                    fig = ns.get("fig")
                    if fig is not None and hasattr(fig, "to_json"):
                        fig_json = fig.to_json()
                except Exception as e:
                    success = False
                    error = f"{{type(e).__name__}}: {{e}}"

                out = {{
                    "success": success,
                    "stdout": stdout_capture.getvalue(),
                    "result_repr": result_repr,
                    "figure_json": fig_json,
                    "error": error,
                }}
                print("___SANDBOX_OUTPUT_START___")
                print(json.dumps(out))
                print("___SANDBOX_OUTPUT_END___")
            """)

            with open(run_script_path, "w", encoding="utf-8") as f:
                f.write(runner_code)

            cmd = [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=512m",
                "--cpus=1",
                "-v", f"{temp_dir}:/data:ro",
                "data-analysis-sandbox:latest",
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s + 5,
            )

            stdout = proc.stdout
            if "___SANDBOX_OUTPUT_START___" in stdout:
                payload = stdout.split("___SANDBOX_OUTPUT_START___")[1].split("___SANDBOX_OUTPUT_END___")[0].strip()
                res = json.loads(payload)
                res["code_run"] = code
                return res

            return {
                "success": False,
                "stdout": stdout,
                "result_repr": None,
                "figure_json": None,
                "error": proc.stderr.strip() or "Docker container execution failed.",
                "code_run": code,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "result_repr": None,
                "figure_json": None,
                "error": f"Docker execution timed out after {self.timeout_s} seconds.",
                "code_run": code,
            }
        except Exception as e:
            # Fallback to subprocess if Docker is not available
            return self._run_subprocess(code, df_pickle_path)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
