# src/agent/nodes/classify_intent.py
from langgraph.types import Command
from langgraph.graph import END
from typing import Literal
from langsmith import traceable

from ..state import AgentState, UserQueryClassification
from ..llm_client import LLMClient
from ...prompt.templates import CLASSIFY_INTENT_SYSTEM

llm_client = LLMClient()


@traceable(name="intent_classification")
def classify_intent_node(state: AgentState) -> Command[Literal[
    "recherche_similaire", "generate_clarification",
    "reponse_hors_sujet", "reponse_politique"
]]:
    messages = [
        {"role": "system", "content": CLASSIFY_INTENT_SYSTEM},
        {"role": "user",   "content": f"Question : {state['user_query']}"}
    ]

    try:
        classification = llm_client.invoke_structured(messages, UserQueryClassification)
    except Exception as e:
        return _handle_classification_error(str(e))

    print(f"\n[Classify Intent] Query: '{state['user_query'][:50]}...'")
    print(f"  → Validity: {classification.request_validity}")
    print(f"  → Nature:   {classification.query_nature.upper()}")
    print(f"  → Chart:    {classification.chart_type}")

    goto = {
        "allowed":          "recherche_similaire",
        "ambiguous":        "generate_clarification",
        "out_of_scope":     "reponse_hors_sujet",
        "policy_violation": "reponse_politique",
    }.get(classification.request_validity, "reponse_hors_sujet")

    return Command(update={"classification": classification}, goto=goto)


def _handle_classification_error(error_msg: str) -> Command:
    print(f"[Error] {error_msg}")
    err_class = UserQueryClassification(
        request_validity="out_of_scope",
        query_nature="simple_retrieval",
        reasoning_summary=f"Erreur système: {error_msg}"
    )
    return Command(
        update={"classification": err_class, "errors": [error_msg]},
        goto="reponse_hors_sujet"
    )


def reponse_hors_sujet_node(state: AgentState) -> Command:
    message = (
        "Désolé, je ne peux pas répondre à cette question car elle ne concerne pas "
        "les élections législatives ivoiriennes ou dépasse les données disponibles.\n\n"
        "Je peux vous renseigner sur : les résultats par région ou circonscription, "
        "les candidats élus, les taux de participation, les statistiques par parti "
        "(RHDP, PDCI, PPA-CI…) et les bulletins blancs/nuls."
    )
    print(f"\n[Out of Scope] Question: '{state['user_query']}'")
    return Command(update={"final_answer": message}, goto=END)


def reponse_politique_node(state: AgentState) -> Command:
    message = (
        "Désolé, cette demande viole la politique d'utilisation de l'agent.\n\n"
        "Je suis limité à la consultation des données électorales : "
        "aucune modification, pas de demandes malveillantes, "
        "pas de financement de campagne, pas de données personnelles sur les électeurs."
    )
    print(f"\n[Policy Violation] Request blocked: '{state['user_query']}'")
    return Command(update={"final_answer": message}, goto=END)