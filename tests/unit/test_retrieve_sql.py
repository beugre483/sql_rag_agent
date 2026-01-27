import pytest
import json
from unittest.mock import patch, mock_open
from src.agent.nodes.retrieve_similar_sql import retrieve_similar_examples
import src.agent.nodes.retrieve_similar_sql as node_module

MOCK_JSON_DATA = [
    {
        "id": 1,
        "question": "vainqueur élection", # Mots-clés purs
        "sql_query": "SELECT nom FROM elus",
        "explication": "Chercher le gagnant."
    },
    {
        "id": 2,
        "question": "taux participation", # Mots-clés purs
        "sql_query": "SELECT taux FROM stats",
        "explication": "Calculer le taux."
    }
]

@pytest.fixture(autouse=True)
def reset_globals():
    node_module._BM25_MODEL = None
    node_module._EXAMPLES_DATA = None

@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(MOCK_JSON_DATA))
def test_retrieve_similar_chooses_correct_example(mock_file):
    """Vérifie que le moteur choisit l'exemple 1 quand on parle de vainqueur."""
    
    # On utilise EXACTEMENT les mots de l'exemple pour garantir un score > 0.5
    state = {"user_query": "vainqueur élection"} 
    
    result = retrieve_similar_examples(state)
    
    # Assertions
    assert "vainqueur" in result.update["similar_examples_context"].lower()
    assert "participation" not in result.update["similar_examples_context"].lower()
    assert result.goto == "generate_sql"

@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(MOCK_JSON_DATA))
def test_retrieve_similar_chooses_participation(mock_file):
    """Vérifie que le moteur choisit l'exemple 2 quand on parle de participation."""
    
    # On utilise EXACTEMENT les mots de l'exemple
    state = {"user_query": "taux participation"} 
    
    result = retrieve_similar_examples(state)
    
    # Assertions
    assert "participation" in result.update["similar_examples_context"].lower()
    assert "vainqueur" not in result.update["similar_examples_context"].lower()
    assert result.goto == "generate_sql"