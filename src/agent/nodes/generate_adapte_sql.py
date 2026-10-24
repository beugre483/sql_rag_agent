# src/agent/nodes/generate_sql.py
from langgraph.types import Command
from typing import Literal
import re
from langsmith import traceable

from ..state import AgentState
from ..llm_client import LLMClient
from ...prompt.templates import GENERATE_SQL_SYSTEM, GENERATE_SQL_HUMAN
from src.ingestion.clean_data import ElectionDataCleaner
from src.database.profiler import load_profile, format_profile_for_prompt

# Client instancié une seule fois au chargement du module
llm_client = LLMClient()

# Profil de la base calculé une fois (cache JSON, recalculé si la base change)
DB_PROFILE = format_profile_for_prompt(load_profile())


def _build_direct_party_seat_count_query(normalized_query: str) -> str | None:
    """Construit localement le SQL des comptages de sièges par parti."""
    parties = ("rhdp", "pdci", "ppa-ci", "ppaci", "fpi")
    seat_terms = ("siege", "siège", "sieges", "sièges")

    if not any(term in normalized_query for term in seat_terms):
        return None

    party = next((item for item in parties if item in normalized_query), None)
    if not party:
        return None

    # La colonne normalisée de la base contient les sigles sans ponctuation.
    party_norm = party.replace("-", "")
    return (
        "SELECT COUNT(*) AS nombre_sieges "
        "FROM vue_elus_uniquement "
        f"WHERE parti_politique_norm LIKE '%{party_norm}%'"
    )


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

    direct_query = _build_direct_party_seat_count_query(normalized_query)
    if direct_query:
        print(f"\n[Generate SQL] SQL direct : {direct_query}")
        return Command(update={"sql_query": direct_query}, goto="verify_sql")

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
        db_profile=DB_PROFILE,
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
