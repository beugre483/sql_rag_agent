# src/agent/nodes/retrieve_similar_examples.py
import json
import os
from rank_bm25 import BM25Okapi
from langgraph.types import Command
from typing import Literal
from ..state import AgentState
from langsmith import traceable


# --- VARIABLES GLOBALES (Cache) ---
_BM25_MODEL = None
_EXAMPLES_DATA = None

# --- LISTE DES MOTS VIDES (STOP WORDS) ---
STOP_WORDS = {
    # 1. Articles et liaisons (Bruit)
    "le", "la", "les", "l'", "un", "une", "des", "du", "de", "d'", 
    "et", "ou", "mais", "donc", "or", "ni", "car", "à", "au", "aux",
    "dans", "sur", "par", "pour", "en", "vers", "avec", "sans", "sous",
    
    # 2. Verbes d'état et pronoms
    "est", "sont", "a", "ont", "avez", "suis", "es", "être", "avoir", "faire",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", 
    "ce", "se", "sa", "son", "ses", "cette", "ces",
    
    # 3. Mots interrogatifs VAGUES
    "quel", "quelle", "quels", "quelles", "est-ce", "qu'est-ce", "que", "quoi", "comment"
}

def preprocess(text: str):
    """Nettoie le texte pour ne garder que les mots clés importants."""
    text = text.lower().replace("'", " ").replace("?", "").replace(".", "").replace(",", "")
    tokens = text.split()
    clean_tokens = [t for t in tokens if t not in STOP_WORDS]
    return clean_tokens

def load_knowledge_base():
    """Charge le JSON et initialise BM25 (une seule fois)."""
    global _BM25_MODEL, _EXAMPLES_DATA
    
    if _BM25_MODEL is not None:
        return _BM25_MODEL, _EXAMPLES_DATA

    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "..", "few_shot_examples", "few_shot_examples.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            _EXAMPLES_DATA = json.load(f)
        
        corpus = [preprocess(ex["question"]) for ex in _EXAMPLES_DATA]
        _BM25_MODEL = BM25Okapi(corpus)
        
        print(f"  ✓ [Retriever] Base chargée : {len(_EXAMPLES_DATA)} exemples.")
    except Exception as e:
        print(f"  ✗ [Retriever] Erreur chargement : {e}")
        _EXAMPLES_DATA = []
        _BM25_MODEL = None
        
    return _BM25_MODEL, _EXAMPLES_DATA


@traceable(name="retrieve_similar_example_sql")
def retrieve_similar_examples(state: AgentState) -> Command[Literal["generate_sql"]]:
    """
    Nœud du graphe : Trouve les 2 meilleurs exemples SQL pour aider le LLM.
    """
    print("\n--- RECHERCHE EXEMPLES (BM25) ---")
    
    user_query = state['user_query']
    bm25, examples = load_knowledge_base()
    
    context_text = ""
    
    if bm25 and examples:
        tokenized_query = preprocess(user_query)
        
        if not tokenized_query:
            return Command(
                update={"similar_examples_context": "Aucun mot-clé pertinent détecté."},
                goto="generate_sql"
            )

        doc_scores = bm25.get_scores(tokenized_query)
        top_indexes = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:2]
        
        found_count = 0
        
        for idx in top_indexes:
            score = doc_scores[idx]
            
            if score > 0.5:
                ex = examples[idx]
                context_text += f"--- EXEMPLE SIMILAIRE (Score: {score:.2f}) ---\n"
                context_text += f"Question : {ex['question']}\n"
                context_text += f"Raisonnement : {ex['explication']}\n"
                context_text += f"SQL : {ex['sql_query']}\n\n"
                found_count += 1
        
        if found_count == 0:
            print("  ℹ Aucun exemple assez proche trouvé.")
            context_text = "Pas d'exemples pertinents disponibles."
        else:
            print(f"  ✓ {found_count} exemple(s) trouvé(s) et injecté(s).")
            
    else:
        context_text = "Erreur technique (Base vide)."

    return Command(
        update={"similar_examples_context": context_text},
        goto="generate_sql"
    )