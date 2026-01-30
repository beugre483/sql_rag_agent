
from langgraph.types import Command
from langgraph.graph import END

from ..llm_client import LLMClient
from langsmith import traceable


from ..state import AgentState
@traceable(name="clarification")
def generate_clarification_node(state: AgentState) -> Command:
    """
    Utilise un LLM pour rédiger une question de clarification personnalisée.
    """
    # On instancie le client (Mistral)
    llm_client = LLMClient() 
    
    user_query = state.get("user_query")
    # On récupère le raisonnement de la classification précédente
    classification = state.get("classification")
    reasoning = classification.reasoning_summary if classification else "La requête est incomplète."
    
    data_context="""SCHÉMA EXACT DE LA BASE DE DONNÉES ÉLECTORALES IVOIRIENNES :

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
"""
    
    prompt = f"""
    Tu es un assistant  electoral pour les élections legislatives de 2025 pour la population ivoirienne,tu ne reponds que pour les legislatives. L'utilisateur a posé une question, mais elle est incomplète ou ambiguë ou vague ou trop large.
    
    QUESTION DE L'UTILISATEUR : "{user_query}"
    RAISON DU BLOCAGE : {reasoning}
    CONNAISSANCE DISPONIBLE:{data_context}
    TACHE : 
    Rédige une réponse courte et polie pour :
    1. Reformuler ce que l'utilisateur cherche.
    2. Expliquer précisément ce qui manque (parfois cest la nature precise d'une circonscription, par exemple il ya agboville commune ou agboville sous-prefectures mais l'utilistaur ne dit rien).
    3. Lui poser une question directe pour l'aider à préciser.
    5.evite de mettre des notes comme ci : Note : Si l'utilisateur mentionne une région, vous pourrez alors préciser que Agboville se trouve dans la région de l'Agnéby-Tiassa, mais cela n'est pas nécessaire ici.)
    donne juste les reponses
    
    RECO : Ne sois pas robotique. Utilise le contexte de sa question. Réponds en français
    ne donne que la reponse, ne soit pas strop bavard.
    Voici les regions de la cote d'ivoire : [   "district autonome d'abidjan" 'district autonome de yamoussoukro' 'folon'
 'gbeke' 'gbokle' 'goh' 'gontougo' 'grands ponts' 'guemon' 'hambol' 
 'haut-sassandra' 'haut- sassandra' 'iffou' 'indenie-djuablin'      
 'kabadougou' 'la me' 'loh-djiboua' 'marahoue' 'moronou' 'nawa' "n'zi"
 'poro' 'san-pedro' 'sud-comoe' 'tonkpi' 'worodougou'
 on dit generalement abidjan au lieu de district autonome d'abidjan]
  
    """
    
    # Appel à Mistral
    response = llm_client.invoke(prompt)
    
    return Command(
        update={"final_answer": response.content},
        goto=END
    )