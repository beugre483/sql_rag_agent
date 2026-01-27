# src/agent/nodes/generate_final_answer_sql.py

from langgraph.types import Command
from langgraph.graph import END 
from langchain_core.prompts import ChatPromptTemplate
from ..state import AgentState
from ..llm_client import LLMClient
from typing import List, Dict, Any
from langsmith import traceable


# Initialisation du client LLM
llm_client = LLMClient()
@traceable(name="generate_final_answer")
def generate_final_answer_node(state: AgentState) -> Command:
    """
    Nœud final : Présente les résultats de façon structurée et compréhensible.
    S'assure que l'interlocuteur distingue les différentes zones (Commune/SP).
    """
    
    # 1. Récupération sécurisée des données
    user_query = state.get('user_query', "")
    sql_results = state.get('sql_results', [])
    
    if not sql_results:
        return Command(
            update={"final_answer": "Aucun résultat trouvé pour cette recherche."},
            goto=END
        )

    # 2. Formatage des données pour le LLM
    formatted_data = _format_results_to_markdown(sql_results)
    
    # 3. Prompt orienté "Présentation Claire"
    system_prompt = """
TU ES UN ASSISTANT ÉLECTORAL EXPERT. 
Ton rôle est de présenter les résultats des législatives ivoiriennes de façon très structurée et facile à lire.

--- RÈGLES DE PRÉSENTATION ---
1. STRUCTURE PAR ZONE : Si les résultats contiennent plusieurs circonscriptions (ex: une Commune et une Sous-Préfecture), sépare-les CLAIREMENT avec des titres ou des listes distinctes.
2. SYNTHÈSE : Ne fais pas de longs paragraphes. Utilise des tirets pour lister les élus.
3. MISE EN FORME : Mets les noms des **ÉLUS** et des **PARTIS** en gras.
4. CLARTÉ : L'interlocuteur doit comprendre immédiatement qui a gagné dans quelle zone, même s'il n'a pas précisé "commune" ou "sous-préfecture" dans sa question.
TRANSPARENCE : Si les résultats SQL contiennent plusieurs circonscriptions différentes pour un même nom (ex: 'Tiapoum COMMUNE' et 'Tiapoum SOUS-PREFECTURE'), mentionne-le clairement. 
   Exemple : "Vous avez posé la question pour Tiapoum, voici les résultats pour la Commune et la Sous-Préfecture :"

5. SYNTHÈSE : Ne te contente pas de lister les données. Fais une phrase naturelle.
   Exemple : "Au RHDP, le candidat X a remporté la victoire avec Y voix

Exemple de structure attendue :
"Voici les résultats pour Agboville :
- **Agboville Commune** : Le gagnant est **NOM** (**PARTI**).
- **Agboville Sous-Préfecture** : L'élu est **NOM** (**PARTI**)."
"""

    human_message = f"""
QUESTION : "{user_query}"
DONNÉES SQL :
{formatted_data}

Présente ces résultats de façon claire pour l'interlocuteur :
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_message)
    ])

    try:
        # 4. Appel LLM
        formatted_prompt = prompt.format()
        response = llm_client.invoke(formatted_prompt)
        
        # Gestion du type de réponse
        if isinstance(response, str):
            final_text = response.strip()
        elif hasattr(response, 'content'):
            final_text = response.content.strip()
        else:
            final_text = str(response).strip()

        return Command(
            update={"final_answer": final_text},
            goto=END
        )

    except Exception as e:
        print(f"  ✗ [Error] : {e}")
        return Command(
            update={"final_answer": "Erreur lors de la mise en forme des résultats."},
            goto=END
        )

def _format_results_to_markdown(results: List[Dict]) -> str:
    """Crée un tableau simple pour que le LLM lise les données."""
    if not results: return "Vide."
    headers = list(results[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = [header_line, separator]
    for row in results[:15]:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)