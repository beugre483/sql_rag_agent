# src/agent/nodes/generate_clarification_node.py
from langgraph.types import Command
from langgraph.graph import END
from langsmith import traceable

from ..state import AgentState
from ..llm_client import LLMClient
from ...prompt.templates import GENERATE_CLARIFICATION_PROMPT


llm_client = LLMClient()


@traceable(name="clarification")
def generate_clarification_node(state: AgentState) -> Command:
    user_query   = state.get("user_query", "")
    classification = state.get("classification")
    reasoning    = (
        classification.reasoning_summary
        if classification
        else "La requête est incomplète."
    )

    prompt = GENERATE_CLARIFICATION_PROMPT.format(
        user_query=user_query,
        reasoning=reasoning,
    )

    messages = [
        {"role": "user", "content": prompt}
    ]

    response = llm_client.invoke(messages)
    content  = response.content if hasattr(response, "content") else str(response)

    return Command(update={"final_answer": content}, goto=END)