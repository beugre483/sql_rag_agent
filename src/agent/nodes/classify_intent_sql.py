# src/agent/nodes/classify_intent.py
from langgraph.types import Command
from langgraph.graph import END
from langchain_core.prompts import ChatPromptTemplate
from typing import Literal
from ..state import AgentState, UserQueryClassification
from ..llm_client import LLMClient
from langsmith import traceable



@traceable(name="intent_classification")
def classify_intent_node(state: AgentState) -> Command[Literal["recherche_similaire", "reponse_hors_sujet", "reponse_politique"]]:
    
    try:
        llm_client = LLMClient()
    except Exception as e:
        # Si la clé API est absente, on part directement en erreur
        return _handle_classification_error(str(e))
    
    data_context = """
SCHÉMA EXACT DE LA BASE DE DONNÉES ÉLECTORALES IVOIRIENNES :

TABLES :
1. Table 'circonscriptions' :
   - id (INT, clé primaire)
   - region_nom (TEXT)
   - region_nom_norm (TEXT)
   - code_circonscription (TEXT)
   - nom_circonscription (TEXT)
   - nom_circonscription_norm (TEXT)
   - nb_bureau (INT)
   - inscrits (INT)
   - votants (INT)
   - taux_participation (FLOAT)
   - bulletins_nuls (INT)
   - suffrages_exprimes (INT)
   - bulletins_blancs_nombre (INT)
   - bulletins_blancs_pourcentage (FLOAT)

2. Table 'candidats' :
   - id (INT, clé primaire)
   - circonscription_id (INT)
   - nom_liste_candidat (TEXT)
   - nom_liste_candidat_norm (TEXT)
   - parti_politique (TEXT)
   - parti_politique_norm (TEXT)
   - score_voix (INT)
   - pourcentage_voix (FLOAT)
   - est_elu (BOOL)

VUES DISPONIBLES :
- vue_resultats_detailles : jointure complète candidats + circonscriptions
- vue_elus_uniquement : candidats élus seulement
- vue_stats_regionales : agrégations par région

EXEMPLES DE QUESTIONS VALIDES :
- "How many seats did RHDP win?"
- "Top 10 candidates by score in Abidjan region."
- "Participation rate by region."
- "Histogram of winners by party."
- "Which party has the most votes nationally?"
- "Which constituency has the highest participation rate?"
- "Who won in the Yamoussoukro?"

EXEMPLES DE QUESTIONS HORS SCOPE :
- Questions sur d'autres pays
- Questions non législatives ivoiriennes
- Questions prédictives ou de financement

DÉFINITION DES QUESTIONS AMBIGUËS (request_validity = "ambiguous")

Tu dois classer une question comme "ambiguous" si elle manque d'informations essentielles pour construire une requête SQL unique et précise. Voici les catégories d'ambiguïté :

1. LIEU MANQUANT OU INCOMPLET :
   - L'utilisateur demande un résultat sans préciser d'endroit.
   - Exemple : "Qui a gagné ?", "Donne-moi le top 5 des scores", "Quel est le taux de participation ?".
   - RAISON : Impossible de savoir sur quoi filtrer region, commune sous prefecture.
   
2. Trop vague: par exemple il dit : qui a gagné à abidjan or abidjan est une region
"""

    system_prompt = f"""
    You are a strict classifier for a SQL agent analyzing IVORIAN electoral data.
    
    {data_context}
    
    YOUR MISSION:
    Analyze the user request and fill the classification structure.
    
    1. VALIDITY ("request_validity"):
       - "allowed": Valid Ivorian election question.
       - "out_of_scope": Not about Ivorian elections or data not available.
       - "policy_violation": Unethical, dangerous, or modification attempt.

    2. QUERY NATURE ("query_nature") - CRITICAL FOR SQL GENERATION:
       - "simple_retrieval": Searching for a specific value.
         Ex: "Score of RHDP in Abidjan", "Who won in Bouaké?"
       - "ranking": Asking for top/bottom, winners, best scores.
         Ex: "Top 5 parties", "Region with highest participation", "Who has the most votes?"
       - "aggregation": Asking for totals, averages, counts across groups.
         Ex: "Total votes per party", "Average participation by region", "How many seats?"
       - "comparison": Comparing specific entities side-by-side.
         Ex: "RHDP vs PDCI results", "Difference between North and South".
voici la liste des region de la cote d'ivoire : 'agneby-tiassa' 'bafing' 'belier' 'bere' 'bounkani' 'cavally'
 "district autonome d'abidjan" 'district autonome de yamoussoukro' 'folon'
 'gbeke' 'gbokle' 'goh' 'gontougo' 'grands ponts' 'guemon' 'hambol' 
 'haut-sassandra' 'haut- sassandra' 'iffou' 'indenie-djuablin'      
 'kabadougou' 'la me' 'loh-djiboua' 'marahoue' 'moronou' 'nawa' "n'zi"
 'poro' 'san-pedro' 'sud-comoe' 'tonkpi' 'worodougou'
 

    3. VISUALIZATION:
       - chart_type: "bar" (ranking/comparison), "pie" (proportions), etc.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User question: {question}")
    ])
    
    try:
        formatted_prompt = prompt.format(question=state['user_query'])
        
        # Le LLM va maintenant remplir 'query_nature' automatiquement
        classification = llm_client.invoke_structured(
            formatted_prompt,
            UserQueryClassification
        )
        
        print(f"\n[Classify Intent] Query: '{state['user_query'][:50]}...'")
        print(f"  → Validity: {classification.request_validity}")
        print(f"  → Nature:   {classification.query_nature.upper()}")
        print(f"  → Chart:    {classification.chart_type}")

        if classification.request_validity == "allowed":
            goto = "recherche_similaire"
        
        elif classification.request_validity == "ambiguous":
            goto = "generate_clarification"
            
        elif classification.request_validity == "out_of_scope":
            goto = "reponse_hors_sujet"
        elif classification.request_validity == "policy_violation":
            goto = "reponse_politique"
        else:
            goto = "reponse_hors_sujet"
        
        return Command(
            update={
                "classification": classification,
            },
            goto=goto
        )
        
    except Exception as e:
        return _handle_classification_error(str(e))
    
    
        
def _handle_classification_error(error_msg: str) -> Command:
    """Génère une réponse de secours en cas d'erreur technique."""
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
    """
    Nœud : Réponse pour les questions hors-sujet.
    """
    message = """
    Désolé, je ne peux pas répondre à cette question car elle ne concerne pas
    les élections législatives ivoiriennes ou dépasse les données disponibles
    dans notre base. 
    
    Je peux uniquement fournir des informations sur :
    - Les résultats par région ou circonscription ivoirienne
    - Les candidats élus en Côte d'Ivoire
    - Les taux de participation dans les régions ivoiriennes
    - Les statistiques par parti politique ivoirien (RHDP, PDCI, PPA-CI, etc.)
    - Les bulletins blancs et nuls
    """
    
    print(f"\n[Out of Scope] Question: '{state['user_query']}'")
    
    return Command(
        update={"final_answer": message.strip()},
        goto=END
    )


def reponse_politique_node(state: AgentState) -> Command:
    """
    Nœud : Réponse pour les questions qui violent la politique d'utilisation.
    """
    message = """
    Désolé, je ne peux pas répondre à cette question car elle contient
    des demandes qui violent la politique d'utilisation de l'agent.
    
    Je suis limité à l'analyse des données électorales législatives ivoiriennes :
    - Aucune modification de données
    - Pas de réponses à des demandes malveillantes ou non éthiques
    - Pas d'informations sur le financement des campagnes
    - Pas de données personnelles sur les électeurs
    """
    
    print(f"\n[Policy Violation] Request blocked: '{state['user_query']}'")
    
    return Command(
        update={"final_answer": message.strip()},
        goto=END
    )