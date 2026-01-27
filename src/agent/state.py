# src/agent/state.py
from typing import Optional, List, Dict, Literal, Annotated
from typing_extensions import TypedDict
import operator

# On garde celui-là en BaseModel car c'est une sortie de LLM
from pydantic import BaseModel, Field

class UserQueryClassification(BaseModel):
    request_validity: Literal["allowed", "out_of_scope", "policy_violation","ambiguous"]
    query_nature: Literal["simple_retrieval", "ranking", "aggregation", "comparison"]
    task_type: Optional[Literal["sql_query", "visualization", "mixed"]] = None
    chart_type: Optional[Literal["bar", "histogram", "pie", "line", "map"]] = None
    reasoning_summary: str=""

# ON CHANGE AgentState EN TypedDict
class AgentState(TypedDict):
    user_query: str
    classification: Optional[UserQueryClassification]
    sql_query: Optional[str]
    sql_results: Optional[List[Dict]]
    chart_generated: bool
    similar_examples_context: str
    chart_data: Optional[Dict]
    final_answer: Optional[str]
    # Annotated permet d'ajouter les erreurs au lieu de les écraser
    errors: Annotated[List[str], operator.add]