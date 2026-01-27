import pytest
from unittest.mock import patch, MagicMock
from src.agent.nodes.classify_intent_sql import classify_intent_node
from src.agent.state import UserQueryClassification

@patch("src.agent.nodes.classify_intent_sql.LLMClient")
def test_classify_intent_allowed(MockClientClass):
    """Teste si une question valide va bien vers recherche_similaire."""
    # Configurer le simulateur (Mock)
    mock_instance = MockClientClass.return_value
    mock_instance.invoke_structured.return_value = UserQueryClassification(
        request_validity="allowed",
        query_nature="simple_retrieval",
        reasoning_summary="Test valide"
    )

    state = {"user_query": "Qui a gagné à Bouaké ?"}
    result = classify_intent_node(state)

    assert result.goto == "recherche_similaire"
    assert result.update["classification"].request_validity == "allowed"

@patch("src.agent.nodes.classify_intent_sql.LLMClient")
def test_classify_intent_ambiguous(MockClientClass):
    """Teste si une question sans lieu va bien vers clarification."""
    mock_instance = MockClientClass.return_value
    mock_instance.invoke_structured.return_value = UserQueryClassification(
        request_validity="ambiguous",
        query_nature="simple_retrieval",
        reasoning_summary="Lieu manquant",
        clarification_message="De quelle ville parlez-vous ?"
    )

    state = {"user_query": "Qui a gagné ?"}
    result = classify_intent_node(state)

    assert result.goto == "generate_clarification"

@patch("src.agent.nodes.classify_intent_sql.LLMClient")
def test_classify_intent_system_error(MockClientClass):
    """Teste la réaction du code si le LLM plante."""
    mock_instance = MockClientClass.return_value
    mock_instance.invoke_structured.side_effect = Exception("Erreur Mistral")

    state = {"user_query": "Question test"}
    result = classify_intent_node(state)

    # Doit rediriger vers hors sujet proprement
    assert result.goto == "reponse_hors_sujet"
    assert "Erreur Mistral" in result.update["errors"][0]