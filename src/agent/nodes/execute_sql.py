# src/agent/nodes/execute_sql.py
from langgraph.types import Command
from typing import Literal
from pathlib import Path
from ..state import AgentState
from src.database.connection import DatabaseConnection
from langsmith import traceable
from langgraph.graph import END 

@traceable(name="sql_execution")
def execute_sql_node(state: AgentState) -> Command[Literal["determine_chart_intent"]]:
    query = state['sql_query']
    
    if not query:
        return Command(
            update={
                "errors": ["Aucune requête à exécuter."],
                "sql_results": [],
                "final_answer": "Désolé, je n'ai pas pu exécuter votre requête. Veuillez reformuler votre question s'il vous plaît."
            },
            goto=END
        )

    print(f"\n[Execute SQL] Exécution de : {query}")

    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    db_path = project_root / "data" / "processed" / "elections.db"
    
    try:
        db = DatabaseConnection(db_path=str(db_path), read_only=True)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            
        print(f"  ✓ {len(results)} lignes récupérées.")
        if results:
            print(f"  ℹ Aperçu : {results[0]}")

        return Command(
            update={"sql_results": results},
            goto="determine_chart_intent"
        )

    except Exception as e:
        print(f"   [Execute SQL Error] : {e}")
        
        return Command(
            update={
                "errors": [f"Erreur d'exécution : {str(e)}"],  # UNE SEULE erreur
                "sql_results": [],
                "final_answer": "Désolé, je n'ai pas pu exécuter votre requête. Veuillez reformuler votre question s'il vous plaît."
            },
            goto=END
        )