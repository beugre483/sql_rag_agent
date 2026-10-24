import pytest
from unittest.mock import patch, MagicMock
from src.agent.nodes.classify_intent_sql import classify_intent_node
from src.agent.state import UserQueryClassification

@patch("src.agent.nodes.classify_intent_sql.llm_client")
def test_classify_intent_allowed(mock_llm):
    """Teste si une question valide va bien vers recherche_similaire."""
    # Configurer le simulateur (Mock)
    mock_llm.invoke_structured.return_value = UserQueryClassification(
        request_validity="allowed",
        query_nature="simple_retrieval",
        reasoning_summary="Test valide"
    )

    state = {"user_query": "Qui a gagné à Bouaké ?"}
    result = classify_intent_node(state)

    assert result.goto == "recherche_similaire"
    assert result.update["classification"].request_validity == "allowed"

@patch("src.agent.nodes.classify_intent_sql.llm_client")
def test_classify_intent_ambiguous(mock_llm):
    """Teste si une question sans lieu va bien vers clarification."""
    mock_llm.invoke_structured.return_value = UserQueryClassification(
        request_validity="ambiguous",
        query_nature="simple_retrieval",
        reasoning_summary="Lieu manquant",
    )

    state = {"user_query": "Qui a gagné ?"}
    result = classify_intent_node(state)

    assert result.goto == "generate_clarification"

@patch("src.agent.nodes.classify_intent_sql.llm_client")
def test_classify_intent_system_error(MockClientClass):
    """Teste la réaction du code si le LLM plante."""
    MockClientClass.invoke_structured.side_effect = Exception("Erreur Mistral")

    state = {"user_query": "Question générale"}
    result = classify_intent_node(state)

    # Doit rediriger vers hors sujet proprement
    assert result.goto == "reponse_hors_sujet"
    assert "Erreur Mistral" in result.update["errors"][0]


@patch("src.agent.nodes.classify_intent_sql.llm_client")
def test_classify_election_query_recovered_from_false_out_of_scope(mock_llm):
    """Une circonscription inconnue du modèle doit rester interrogeable."""
    mock_llm.invoke_structured.return_value = UserQueryClassification(
        request_validity="out_of_scope",
        query_nature="simple_retrieval",
        reasoning_summary="Lieu inconnu",
    )

    result = classify_intent_node({"user_query": "Qui a gagné à Tiapoum ?"})

    assert result.goto == "recherche_similaire"
    assert result.update["classification"].request_validity == "allowed"
