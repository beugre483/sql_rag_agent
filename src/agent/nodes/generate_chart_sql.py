# src/agent/nodes/generate_chart.py

import matplotlib.pyplot as plt
import io
import base64
from langgraph.types import Command
from langgraph.graph import END
from typing import Literal, List, Dict

from ..state import AgentState
from langsmith import traceable



@traceable(name="determine_chart_intent")
def determine_chart_intent_node(state: AgentState) -> Command[Literal["generate_chart", "generate_final_answer"]]:
    """
    Décide si on doit générer un graphique ou passer directement à la réponse texte.
    Condition : 
    1. L'intention (classification) demande une visualisation.
    2. On a des résultats SQL non vides.
    """
    
    # Récupération des infos du state
    classification = state['classification']
    results = state['sql_results']
    
    should_generate = False
    
    # Vérification 1 : Est-ce que l'utilisateur voulait un graph ?
    # On regarde task_type OU si chart_type est défini
    if classification:
        if classification.task_type in ["visualization", "mixed"] or classification.chart_type is not None:
            should_generate = True
            
    # Vérification 2 : A-t-on des données à afficher ?
    if not results or len(results) == 0:
        print("[Chart Intent] Pas de données -> Annulation du graphique.")
        should_generate = False

    if should_generate:
        print(f"[Chart Intent] Graphique demandé : {classification.chart_type}")
        return Command(goto="generate_chart")
    else:
        print("[Chart Intent] Pas de graphique nécessaire -> Réponse texte.")
        return Command(goto="generate_final_answer")


@traceable(name="chart_generation")
def generate_chart_node(state: AgentState) -> Command[Literal["generate_final_answer"]]:
    """
    Génère le graphique demandé et stocke l'image (base64 ou path) dans le state.
    """
    chart_type = state['classification'].chart_type
    data = state['sql_results']
    
    print(f"\n[Generate Chart] Création d'un graphique type : {chart_type}")
    
    chart_data = None
    
    try:
        # --- SÉLECTION DE LA FONCTION SELON LE TYPE ---
        if chart_type == "bar":
            chart_data = _create_bar_chart(data)
        elif chart_type == "pie":
            chart_data = _create_pie_chart(data)
        elif chart_type == "histogram":
            chart_data = _create_bar_chart(data) # Souvent similaire en SQL simple
        else:
            # Par défaut, on tente un bar chart si le type est inconnu
            chart_data = _create_bar_chart(data)
            
        return Command(
            update={
                "chart_generated": True,
                "chart_data": chart_data # Contient l'image en base64 pour le frontend
            },
            goto="generate_final_answer"
        )
        
    except Exception as e:
        print(f"[Chart Error] Impossible de générer le graph : {e}")
        # On continue sans graph, pas grave
        return Command(
            update={"chart_generated": False, "errors": [f"Erreur Graphique: {e}"]},
            goto="generate_final_answer"
        )


def _prepare_data_for_plotting(data: List[Dict]):
    """
    Essaie de deviner intelligemment qui est X (labels) et qui est Y (valeurs).
    Heuristique : 
    - X = Première colonne de type texte trouvée.
    - Y = Première colonne de type nombre trouvée.
    """
    if not data: return None, None, None, None
    
    keys = list(data[0].keys())
    
    label_key = None
    value_key = None
    
    # Recherche heuristique
    for k in keys:
        val = data[0][k]
        if isinstance(val, str) and not label_key:
            label_key = k
        elif isinstance(val, (int, float)) and not value_key:
            value_key = k
            
    # Fallback si on ne trouve pas
    if not label_key: label_key = keys[0]
    if not value_key and len(keys) > 1: value_key = keys[1]
    
    # Extraction des listes
    labels = [str(row[label_key]) for row in data]
    values = [row[value_key] for row in data]
    
    return labels, values, label_key, value_key

def _create_bar_chart(data: List[Dict]) -> Dict:
    """Génère un Barchart et renvoie l'image en base64."""
    labels, values, x_label, y_label = _prepare_data_for_plotting(data)
    
    if not values: raise ValueError("Pas de données numériques trouvées pour le graphique.")

    plt.figure(figsize=(10, 6))
    
    # Création du bar chart
    bars = plt.bar(labels, values, color='#4CAF50')
    
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(f"{y_label} par {x_label}")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Sauvegarde en mémoire
    return _fig_to_base64(plt)

def _create_pie_chart(data: List[Dict]) -> Dict:
    """Génère un Piechart."""
    labels, values, _, _ = _prepare_data_for_plotting(data)
    
    if not values: raise ValueError("Pas de données numériques.")

    plt.figure(figsize=(8, 8))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140)
    plt.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
    
    return _fig_to_base64(plt)

def _fig_to_base64(plt_obj) -> Dict:
    """Convertit la figure Matplotlib en string base64 pour l'envoi."""
    img = io.BytesIO()
    plt_obj.savefig(img, format='png')
    img.seek(0)
    b64_string = base64.b64encode(img.read()).decode('utf-8')
    plt_obj.close()
    
    return {
        "mime_type": "image/png",
        "data": b64_string
    }