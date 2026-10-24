# src/agent/nodes/generate_final_answer_sql.py
from langgraph.types import Command
from langgraph.graph import END
from typing import List, Dict
from langsmith import traceable

from ..state import AgentState
from ..llm_client import LLMClient


@traceable(name="generate_final_answer")
def generate_final_answer_node(state: AgentState) -> Command:
    user_query  = state.get("user_query", "")
    sql_results = state.get("sql_results", [])

    if not sql_results:
        return Command(
            update={"final_answer": "Aucun résultat trouvé. Veuillez reformuler votre question."},
            goto=END
        )

    # Les résultats SQL sont déjà structurés : les afficher directement évite
    # un troisième appel réseau au LLM et rend le chat beaucoup plus réactif.
    return Command(
        update={"final_answer": _format_results_to_markdown(sql_results)},
        goto=END,
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
