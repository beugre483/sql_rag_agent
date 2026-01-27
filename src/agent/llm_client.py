# src/agent/llm_client.py
import os
from langchain_mistralai import ChatMistralAI
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    def __init__(self, model_name="mistral-small-latest"):
        """
        Client LLM pour interagir avec Mistral AI
        
        Variables d'environnement requises:
        - MISTRAL_API_KEY: Clé API Mistral (format: "xxxxxx")
        """
        api_key = os.getenv("MISTRAL_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Clé API Mistral non trouvée. "
                "Définissez la variable d'environnement MISTRAL_API_KEY."
            )
        
        self.llm = ChatMistralAI(
            model=model_name,
            api_key=api_key,
            temperature=0
        )

    def invoke(self, prompt):
        """Appel simple du LLM"""
        return self.llm.invoke(prompt)
    
    def invoke_structured(self, prompt, schema):
        """
        Appel avec structured output
        
        Args:
            prompt: Prompt à envoyer
            schema: Classe Pydantic définissant le format de sortie
        """
        try:
            # Méthode 1: Avec with_structured_output
            structured_llm = self.llm.with_structured_output(schema)
            return structured_llm.invoke(prompt)
        except Exception as e:
            # Fallback si la méthode échoue
            print(f"Erreur structured output: {e}")
            
            # Méthode alternative: Utiliser invoke avec parsing
            response = self.llm.invoke(prompt)
            # Ici tu peux ajouter un parsing manuel si nécessaire
            return response

