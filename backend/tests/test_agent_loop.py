from langchain_core.messages import AIMessage, ToolMessage
from backend.agent.self_correct import run_with_self_correction, parse_tool_result


class MockAgent:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def invoke(self, inputs):
        idx = min(self.call_count, len(self.responses) - 1)
        resp = self.responses[idx]
        self.call_count += 1
        return resp


def test_parse_tool_result():
    # Dict
    assert parse_tool_result({"success": True}) == {"success": True}
    # JSON String
    assert parse_tool_result('{"success": true, "result_repr": "42"}') == {
        "success": True,
        "result_repr": "42",
    }
    # Python Dict String
    assert parse_tool_result("{'success': False, 'error': 'SyntaxError'}") == {
        "success": False,
        "error": "SyntaxError",
    }


def test_agent_loop_direct_answer():
    # Agent answers without execute_python tool call
    agent = MockAgent([
        {
            "messages": [
                AIMessage(content="This dataset contains 100 rows and 5 columns.")
            ]
        }
    ])

    result = run_with_self_correction(agent, "How many rows are there?", [])

    assert result["attempts"] == 1
    assert result["answer"] == "This dataset contains 100 rows and 5 columns."
    assert result["figure_json"] is None
    assert result["code_run"] is None


def test_agent_loop_self_corrects_on_second_attempt():
    # Attempt 1: Fails with KeyError
    fail_ai_msg = AIMessage(
        content="Let me compute the total.",
        tool_calls=[{
            "name": "execute_python",
            "args": {"code": "result = df['missing_col'].sum()"},
            "id": "call_1",
            "type": "tool_call",
        }]
    )
    fail_tool_msg = ToolMessage(
        content='{"success": false, "error": "KeyError: missing_col"}',
        name="execute_python",
        tool_call_id="call_1",
    )

    # Attempt 2: Succeeds
    success_ai_msg = AIMessage(
        content="The total sales is $500.",
        tool_calls=[{
            "name": "execute_python",
            "args": {"code": "result = df['sales'].sum()"},
            "id": "call_2",
            "type": "tool_call",
        }]
    )
    success_tool_msg = ToolMessage(
        content='{"success": true, "result_repr": "500", "figure_json": null}',
        name="execute_python",
        tool_call_id="call_2",
    )
    final_ai_msg = AIMessage(content="The total sales is $500.")

    agent = MockAgent([
        {"messages": [fail_ai_msg, fail_tool_msg]},
        {"messages": [success_ai_msg, success_tool_msg, final_ai_msg]},
    ])

    result = run_with_self_correction(agent, "What is the total sales?", [])

    assert result["attempts"] == 2
    assert "total sales is $500" in result["answer"]
    assert result["code_run"] == "result = df['sales'].sum()"


def test_agent_loop_exhausts_retries():
    # All attempts fail
    fail_ai_msg = AIMessage(
        content="Computing...",
        tool_calls=[{
            "name": "execute_python",
            "args": {"code": "invalid_syntax(("},
            "id": "call_err",
            "type": "tool_call",
        }]
    )
    fail_tool_msg = ToolMessage(
        content='{"success": false, "error": "SyntaxError: unmatched ("}',
        name="execute_python",
        tool_call_id="call_err",
    )

    agent = MockAgent([
        {"messages": [fail_ai_msg, fail_tool_msg]},
        {"messages": [fail_ai_msg, fail_tool_msg]},
        {"messages": [fail_ai_msg, fail_tool_msg]},
    ])

    result = run_with_self_correction(agent, "Analyze this", [])

    assert result["attempts"] == 3
    assert "unable to complete the analysis after 3 attempts" in result["answer"]
    assert "SyntaxError" in result["answer"]


def test_agent_loop_refuses_off_topic_query():
    # When an off-topic question is asked, the agent directly returns the refusal message
    refusal_text = "I can only answer questions related to your uploaded spreadsheet dataset. Please ask a question about the data."
    agent = MockAgent([
        {
            "messages": [
                AIMessage(content=refusal_text)
            ]
        }
    ])

    result = run_with_self_correction(agent, "Who was the first president of the United States?", [])

    assert result["attempts"] == 1
    assert "only answer questions related to your uploaded spreadsheet dataset" in result["answer"]
    assert result["figure_json"] is None
    assert result["code_run"] is None

