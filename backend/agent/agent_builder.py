import os
from typing import Any, Optional
import pandas as pd
from langchain.agents import create_agent

try:
    from backend.agent.prompts import SYSTEM_PROMPT
    from backend.agent.tools import make_execute_python_tool
    from backend.config import settings
except ImportError:
    from agent.prompts import SYSTEM_PROMPT
    from agent.tools import make_execute_python_tool
    from config import settings


def get_llm():
    provider = (settings.llm_provider or "groq").lower().strip()
    groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")
    mistral_key = settings.mistral_api_key or os.environ.get("MISTRAL_API_KEY")

    if provider == "mistral" or (mistral_key and not groq_key):
        if not mistral_key:
            raise ValueError(
                "Mistral API key is missing. Please set MISTRAL_API_KEY in your .env file."
            )
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=settings.model_name if "mistral" in settings.model_name else "mistral-large-latest",
            api_key=mistral_key,
            temperature=0,
        )
    else:
        if not groq_key:
            raise ValueError(
                "Groq API key is missing. Please set GROQ_API_KEY in your .env file."
            )
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.model_name if settings.model_name else "llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0,
        )


def build_agent(df: pd.DataFrame, profile_str: str, pickle_path: Optional[str] = None):
    llm = get_llm()
    exec_tool = make_execute_python_tool(
        df,
        sandbox_timeout=settings.sandbox_timeout_seconds,
        pickle_path=pickle_path,
    )
    agent = create_agent(
        model=llm,
        tools=[exec_tool],
        system_prompt=SYSTEM_PROMPT.format(schema=profile_str),
    )
    return agent
