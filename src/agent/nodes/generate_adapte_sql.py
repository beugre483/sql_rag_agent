# src/agent/nodes/generate_sql.py
from langgraph.types import Command
from typing import Literal
import re
from langsmith import traceable

from ..state import AgentState
from ..llm_client import LLMClient
from ...prompt.templates import GENERATE_SQL_SYSTEM, GENERATE_SQL_HUMAN
from src.ingestion.clean_data import ElectionDataCleaner

# Client instancié une seule fois au chargement du module
llm_client = LLMClient()


@traceable(name="sql_generation")
def generate_sql_query_node(state: AgentState) -> Command[Literal["verify_sql"]]:
    user_query      = state.get("user_query", "")
    errors          = state.get("errors", [])
    classification  = state.get("classification")
    similar_context = state.get("similar_examples_context", "")

    # Normalisation de la requête utilisateur
    try:
        normalized_query = ElectionDataCleaner.normalize_text(user_query)
    except Exception:
        normalized_query = user_query.lower().strip()

    error_feedback = (
        f"\nERREUR PRÉCÉDENTE À CORRIGER : {errors[-1]}\n" if errors else ""
    )
    query_nature = (
        classification.query_nature
        if classification and hasattr(classification, "query_nature")
        else "simple_retrieval"
    )

    # Formatage au dernier moment, juste avant l'appel LLM
    system_prompt = GENERATE_SQL_SYSTEM.format(
        error_feedback=error_feedback,
        similar_context=similar_context or "Aucun exemple, suis le schéma à la lettre.",
    )
    human_message = GENERATE_SQL_HUMAN.format(
        user_query=user_query,
        normalized_query=normalized_query,
        query_nature=query_nature,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": human_message},
    ]

    try:
        response = llm_client.invoke(messages)
        raw_sql  = response.content.strip() if hasattr(response, "content") else str(response).strip()
        clean_sql = _clean_sql_output(raw_sql)

        print(f"\n[Generate SQL] SQL produit : {clean_sql}")
        return Command(update={"sql_query": clean_sql}, goto="verify_sql")

    except Exception as e:
        print(f"  ✗ [Error] : {e}")
        return Command(update={"sql_query": None, "errors": [str(e)]}, goto="verify_sql")


def _clean_sql_output(text: str) -> str:
    """Supprime les blocs Markdown et n'extrait que le SELECT/WITH."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
    match = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    if match:
        text = text[match.start():]
    return text.split(";")[0].strip()