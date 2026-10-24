# src/agent/nodes/classify_intent.py
from langgraph.types import Command
from langgraph.graph import END
from typing import Literal
from langsmith import traceable

from ..state import AgentState, UserQueryClassification
from ..llm_client import LLMClient
from ...prompt.templates import CLASSIFY_INTENT_SYSTEM

llm_client = LLMClient()

# Le modèle ne connaît pas nécessairement toutes les communes et
# circonscriptions. Ces termes indiquent néanmoins sans ambiguïté une demande
# d'analyse électorale qui peut être convertie en SQL (avec un LIKE large).
ELECTION_QUERY_SIGNALS = (
    "election", "élection", "legislative", "législative",
    "candidat", "parti", "rhdp", "pdci", "ppa-ci", "ppaci",
    "siege", "siège", "elu", "élu", "gagn", "vote", "voix",
    "participation", "bulletin", "circonscription", "commune",
    "sous-prefecture", "sous-préfecture", "score",
)


def _looks_like_election_query(user_query: str) -> bool:
    """Détecte les questions électorales que le classificateur ne doit pas rejeter.

    Cette vérification ne remplace pas le LLM : elle empêche seulement un faux
    « hors sujet » lorsqu'une commune ou une formulation n'est pas dans ses
    exemples.
    """
    normalized_query = user_query.lower()
    return any(signal in normalized_query for signal in ELECTION_QUERY_SIGNALS)


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
        return _handle_classification_error(state["user_query"], str(e))

    # Une ville inconnue de la liste fournie au prompt reste interrogable dans
    # la base. Ne pas la traiter comme une donnée indisponible.
    if (
        classification.request_validity == "out_of_scope"
        and _looks_like_election_query(state["user_query"])
    ):
        classification = classification.model_copy(
            update={
                "request_validity": "allowed",
                "reasoning_summary": (
                    "Demande électorale reconnue par le filet de sécurité "
                    "déterministe."
                ),
            }
        )

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


def _handle_classification_error(user_query: str, error_msg: str) -> Command:
    print(f"[Error] {error_msg}")

    # Si le service de classification est momentanément indisponible, une
    # demande clairement électorale doit continuer vers le SQL au lieu d'être
    # présentée à tort comme « hors sujet ».
    if _looks_like_election_query(user_query):
        fallback_class = UserQueryClassification(
            request_validity="allowed",
            query_nature="simple_retrieval",
            reasoning_summary="Classification de secours après erreur du modèle.",
        )
        return Command(
            update={"classification": fallback_class, "errors": [error_msg]},
            goto="recherche_similaire",
        )

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
