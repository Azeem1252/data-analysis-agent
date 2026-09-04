import ast
import json
from typing import Any, Optional
try:
    from backend.agent.prompts import RETRY_PROMPT
    from backend.config import settings
except ImportError:
    from agent.prompts import RETRY_PROMPT
    from config import settings


def parse_tool_result(content: Any) -> dict[str, Any]:
    """Parse tool result content into a Python dictionary."""
    if isinstance(content, dict):
        return content

    if isinstance(content, str):
        content_str = content.strip()
        # Try JSON parsing
        try:
            parsed = json.loads(content_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try Python AST literal eval
        try:
            parsed = ast.literal_eval(content_str)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

        return {
            "success": False,
            "error": content_str or "Empty tool result",
        }

    return {
        "success": False,
        "error": f"Invalid tool result type: {type(content).__name__}",
    }


def extract_code_from_tool_calls(tool_calls: list) -> Optional[str]:
    """Extract python code string from tool calls."""
    if not tool_calls:
        return None

    last_call = tool_calls[-1]
    if isinstance(last_call, dict):
        args = last_call.get("args", {})
        if isinstance(args, dict):
            return args.get("code")
    elif hasattr(last_call, "tool_calls") and last_call.tool_calls:
        tc = last_call.tool_calls[-1]
        if isinstance(tc, dict):
            return tc.get("args", {}).get("code")
    return None


def run_with_self_correction(
    agent: Any,
    question: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Runs agent with self-correction up to max_retries attempts on code failure."""
    messages = list(history) + [{"role": "user", "content": question}]

    last_error = None
    last_code = None
    attempts = 0

    for attempt in range(1, settings.max_retries + 1):
        attempts = attempt

        try:
            result = agent.invoke({"messages": messages})
        except Exception as e:
            return {
                "answer": f"Agent execution error: {type(e).__name__}: {e}",
                "figure_json": None,
                "code_run": None,
                "attempts": attempt,
            }

        res_messages = result.get("messages", [])
        if not res_messages:
            return {
                "answer": "No response returned by agent.",
                "figure_json": None,
                "code_run": None,
                "attempts": attempt,
            }

        # Find tool calls and tool output messages
        tool_call_messages = [m for m in res_messages if getattr(m, "tool_calls", None)]
        exec_results = [m for m in res_messages if getattr(m, "name", "") == "execute_python"]

        # If no code execution tool was called, return the final message directly
        if not exec_results:
            final_content = res_messages[-1].content
            return {
                "answer": final_content if isinstance(final_content, str) else str(final_content),
                "figure_json": None,
                "code_run": None,
                "attempts": attempt,
            }

        # Extract code that was run
        if tool_call_messages:
            last_tc = tool_call_messages[-1]
            tcs = getattr(last_tc, "tool_calls", [])
            if tcs and isinstance(tcs, list):
                last_code = tcs[-1].get("args", {}).get("code")

        # Parse tool output
        last_tool_output = parse_tool_result(exec_results[-1].content)

        # Successful execution
        if last_tool_output.get("success"):
            final_answer = res_messages[-1].content
            return {
                "answer": final_answer if isinstance(final_answer, str) else str(final_answer),
                "figure_json": last_tool_output.get("figure_json"),
                "code_run": last_code or last_tool_output.get("code_run"),
                "attempts": attempt,
            }

        # Tool execution failed -> Retry
        last_error = last_tool_output.get("error", "Unknown execution error.")

        if attempt < settings.max_retries:
            # Append failed code and error to continue dialogue
            messages = list(res_messages) + [
                {
                    "role": "user",
                    "content": RETRY_PROMPT.format(
                        error=last_error,
                        code=last_code or "(unknown code)",
                        attempt=attempt + 1,
                        max_retries=settings.max_retries,
                    ),
                }
            ]

    # Exceeded max retries
    return {
        "answer": (
            f"I was unable to complete the analysis after {settings.max_retries} attempts. "
            f"Last encountered error: {last_error}"
        ),
        "figure_json": None,
        "code_run": last_code,
        "attempts": attempts,
    }
