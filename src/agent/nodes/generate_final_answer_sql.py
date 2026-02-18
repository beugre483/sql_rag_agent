# src/agent/nodes/generate_final_answer_sql.py
from langgraph.types import Command
from langgraph.graph import END
from typing import List, Dict
from langsmith import traceable

from ..state import AgentState
from ..llm_client import LLMClient
from ...prompt.templates import GENERATE_FINAL_ANSWER_SYSTEM, GENERATE_FINAL_ANSWER_HUMAN

# Client instancié une seule fois au chargement du module
llm_client = LLMClient()


@traceable(name="generate_final_answer")
def generate_final_answer_node(state: AgentState) -> Command:
    user_query  = state.get("user_query", "")
    sql_results = state.get("sql_results", [])

    if not sql_results:
        return Command(
            update={"final_answer": "Aucun résultat trouvé. Veuillez reformuler votre question."},
            goto=END
        )

    # Formatage des données brutes → tableau markdown, au dernier moment
    formatted_data = _format_results_to_markdown(sql_results)

    human_message = GENERATE_FINAL_ANSWER_HUMAN.format(
        user_query=user_query,
        formatted_data=formatted_data,
    )

    messages = [
        {"role": "system", "content": GENERATE_FINAL_ANSWER_SYSTEM},
        {"role": "user",   "content": human_message},
    ]

    try:
        response   = llm_client.invoke(messages)
        final_text = response.content.strip() if hasattr(response, "content") else str(response).strip()
        return Command(update={"final_answer": final_text}, goto=END)

    except Exception as e:
        print(f"  ✗ [Error] : {e}")
        return Command(
            update={"final_answer": "Erreur lors de la mise en forme des résultats."},
            goto=END
        )


def _format_results_to_markdown(results: List[Dict]) -> str:
    """Convertit les résultats SQL bruts en tableau Markdown pour le LLM."""
    if not results:
        return "Vide."
    headers     = list(results[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    separator   = "| " + " | ".join(["---"] * len(headers)) + " |"
    rows        = [
        "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
        for row in results[:15]
    ]
    return "\n".join([header_line, separator] + rows)