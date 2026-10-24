# tests/test_generate_sql.py
import pytest
from unittest.mock import patch, MagicMock
from src.agent.nodes.generate_adapte_sql import generate_sql_query_node
from src.agent.state import UserQueryClassification



@patch("src.agent.nodes.generate_adapte_sql.llm_client")
@patch("src.agent.nodes.generate_adapte_sql.ElectionDataCleaner")
def test_generate_sql_simple_retrieval(MockCleaner, mock_llm):
    """Cas nominal : génère un SELECT et va vers verify_sql."""
    MockCleaner.normalize_text.return_value = "qui a gagne a bouake ?"

    mock_response = MagicMock()
    mock_response.content = "SELECT * FROM vue_resultats_detailles WHERE nom_circonscription_norm LIKE '%bouake%'"
    mock_llm.invoke.return_value = mock_response

    classification = UserQueryClassification(
        request_validity="allowed",
        query_nature="simple_retrieval",
        reasoning_summary="OK"
    )
    state = {
        "user_query": "Qui a gagné à Bouaké ?",
        "classification": classification,
        "errors": [],
        "similar_examples_context": "",
    }

    result = generate_sql_query_node(state)

    # La valeur nettoyée doit apparaître dans le prompt humain
    called_messages = mock_llm.invoke.call_args[0][0]
    human_content = called_messages[1]["content"]
    assert "qui a gagne a bouake ?" in human_content

    assert result.goto == "verify_sql"
    assert "SELECT" in result.update["sql_query"]
    assert result.update.get("errors") is None


@patch("src.agent.nodes.generate_adapte_sql.llm_client")
@patch("src.agent.nodes.generate_adapte_sql.ElectionDataCleaner")
def test_generate_sql_injects_error_feedback(MockCleaner, mock_llm):
    """Si l'état contient des erreurs, le feedback doit être injecté dans le prompt."""
    # normalize_text reçoit la phrase entière
    MockCleaner.normalize_text.return_value = "combien de sieges pour le rhdp ?"

    mock_response = MagicMock()
    mock_response.content = "SELECT COUNT(*) FROM vue_elus_uniquement WHERE parti_politique_norm LIKE '%rhdp%'"
    mock_llm.invoke.return_value = mock_response

    state = {
        "user_query": "Combien de sièges pour le RHDP ?",
        "classification": None,
        "errors": ["no such column: mauvaise_colonne"],
        "similar_examples_context": "",
    }

    result = generate_sql_query_node(state)

    called_messages = mock_llm.invoke.call_args[0][0]
    system_content = called_messages[0]["content"]
    assert "mauvaise_colonne" in system_content
    assert result.goto == "verify_sql"


@patch("src.agent.nodes.generate_adapte_sql.llm_client")
@patch("src.agent.nodes.generate_adapte_sql.ElectionDataCleaner")
def test_generate_sql_cleans_markdown_blocks(MockCleaner, mock_llm):
    """Le LLM renvoie parfois du SQL encadré de ```sql. Il doit être nettoyé."""
    MockCleaner.normalize_text.return_value = "participation a abidjan"

    mock_response = MagicMock()
    mock_response.content = "```sql\nSELECT * FROM vue_stats_regionales\n```"
    mock_llm.invoke.return_value = mock_response

    state = {
        "user_query": "Participation à Abidjan",
        "classification": None,
        "errors": [],
        "similar_examples_context": "",
    }

    result = generate_sql_query_node(state)

    assert "```" not in result.update["sql_query"]
    assert result.update["sql_query"].startswith("SELECT")


@patch("src.agent.nodes.generate_adapte_sql.llm_client")
@patch("src.agent.nodes.generate_adapte_sql.ElectionDataCleaner")
def test_generate_sql_llm_exception(MockCleaner, mock_llm):
    """Si le LLM plante, le nœud renvoie quand même vers verify_sql avec sql_query=None."""
    MockCleaner.normalize_text.return_value = "top 5 partis"
    mock_llm.invoke.side_effect = Exception("Timeout LLM")

    state = {
        "user_query": "Top 5 partis",
        "classification": None,
        "errors": [],
        "similar_examples_context": "",
    }

    result = generate_sql_query_node(state)

    assert result.goto == "verify_sql"
    assert result.update["sql_query"] is None
    assert "Timeout LLM" in result.update["errors"][0]