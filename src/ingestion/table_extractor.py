import os
import unicodedata
import pandas as pd
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from llama_cloud_services import LlamaExtract 
from llama_cloud_services.extract import ExtractConfig, ExtractMode, ExtractTarget

load_dotenv()



class Candidat(BaseModel):
    parti_politique: Optional[str] = Field(default=None, description="Groupement politique (ex: RHDP, PDCI-RDA, INDEPENDANT).")
    nom_liste_candidat: str = Field(description="Nom du candidat ou de la liste")
    score_voix: int = Field(description="Nombre de voix obtenu")
    pourcentage_voix: float = Field(description="Pourcentage de voix (nombre décimal)")
    est_elu: bool = Field(default=False)

    @field_validator('est_elu', mode='before')
    @classmethod
    def convert_elu(cls, v):
        if v is None: return False
        if isinstance(v, str):
            return "ELU" in v.upper()
        return bool(v)

class Circonscription(BaseModel):

    region_nom: Optional[str] = Field(
        default=None,
        description=(
            "Nom de la région (ex: GBOKLE, NAWA, AGNEBY-TIASSA). "
            "ATTENTION : Ce champ est à l'extrême gauche. "
            "Si la cellule est vide (fusionnée avec la ligne du dessus), laisser vide (null). "
            "INTERDICTION : Ne jamais mettre le code numérique (ex: 067, 001) ici. "
            "Ce champ doit contenir uniquement du TEXTE."
        )
    )
    
    code_circonscription: str = Field(
        description="Le Code numérique de 3 chiffres situé juste à gauche du nom de la circonscription (ex: 001, 067, 123)."
    )
    
    nom_circonscription: str = Field(description="Nom de la circonscription (ex: BAYOTA, DAHIEPA-KEHI...) sans le code numérique.")
    nb_bureaux_vote: int = Field(description="NB BV (Nombre de bureaux de vote)")
    inscrits: int = Field(description="Nombre d'INSCRITS")
    votants: int = Field(description="Nombre de VOTANTS")
    taux_participation: float = Field(description="TAUX DE PART (Pourcentage)")
    bulletins_nuls: int = Field(description="BULL. NULS")
    suffrages_exprimes: int = Field(description="SUF. EXPRIMES")
    bulletins_blancs_nombre: int = Field(description="BULL. BLANCS NOMBRE")
    bulletins_blancs_pourcentage: float = Field(description="BULL. BLANCS %")
    liste_candidats: List[Candidat] = Field(description="Liste des candidats et leurs résultats pour cette circonscription")

    # --- NOUVEAU VALIDATEUR DE SÉCURITÉ ---
    @field_validator('region_nom', mode='before')
    @classmethod
    def validate_region_is_text(cls, v):
        """Si le modèle capture un nombre (ex: '067') au lieu du nom, on le force à None."""
        if v is None:
            return None
        v_str = str(v).strip()
        
        # Si c'est vide ou si c'est un nombre (ex: "067", "67"), on rejette
        if not v_str or v_str.isdigit() or v_str.replace('.', '').isdigit():
            return None
            
        return v_str

class ResultatsElection(BaseModel):
    resultats: List[Circonscription]







class PDFElectionExtractor:
    def __init__(self, api_key: str):
        self.client = LlamaExtract(api_key=api_key)
        self.data = []

    async def extract_from_pdf(self, pdf_path: str):
        """
        Extrait les données et préserve strictement l'ordre du PDF.
        """
        config = ExtractConfig(
            extraction_mode=ExtractMode.PREMIUM,
            extraction_target=ExtractTarget.PER_TABLE_ROW,
            parse_model="anthropic-sonnet-4.5"
        )
        
        # LlamaExtract renvoie généralement les pages dans l'ordre (0, 1, 2...)
        response = await self.client.aextract(
            data_schema=ResultatsElection,
            files=[pdf_path],
            config=config
        )

        # On aplatit la liste page par page, dans l'ordre reçu
        raw_list = []
        for page in response.data:
            if "resultats" in page:
                raw_list.extend(page["resultats"])
        
        # On propage (remplit les vides) sans changer l'ordre
        self.data = self._propagate_regions(raw_list)

        return self.data

    def _propagate_regions(self, items: List[dict]) -> List[dict]:
        last_valid_region = "INCONNUE"
        processed_data = []

        for item in items:
            original_region = item.get("region_nom")
            
            # Nettoyage
            current_region = str(original_region).strip().upper() if original_region else ""
            
            # Vérification : Est-ce une vraie région ?
            # On rejette les nombres (ex: "067") et les vides
            is_numeric = current_region.replace('.', '').isdigit()
            is_valid = (
                current_region 
                and current_region not in ["REGION_MANQUANTE", "999", "NONE", "NULL", "NAN"]
                and not is_numeric 
                and len(current_region) > 2 
            )
            
            if is_valid:
                last_valid_region = current_region
            else:
                # Si région vide ou invalide, on prend la précédente
                item["region_nom"] = last_valid_region
            
            processed_data.append(item)
        
        return processed_data

    def to_dataframe(self) -> pd.DataFrame:
        flat_data = []
        for item in self.data:
            try:
                # Validation Pydantic
                circo = Circonscription(**item)
                base_info = circo.model_dump(exclude={"liste_candidats"})
                
                for cand in circo.liste_candidats:
                    row = {**base_info, **cand.model_dump()}
                    flat_data.append(row)
            except Exception as e:
                print(f"Ligne ignorée (erreur format): {e}")
                continue
        
        df = pd.DataFrame(flat_data)
        
        # Normalisation des noms de colonnes si nécessaire
        if not df.empty:
            if "region_nom_norm" not in df.columns and "region_nom" in df.columns:
                df["region_nom_norm"] = df["region_nom"].str.upper()
            if "nom_circonscription_norm" not in df.columns and "nom_circonscription" in df.columns:
                df["nom_circonscription_norm"] = df["nom_circonscription"].str.upper()
        
        # --- IMPORTANT : AUCUN TRI ICI ---
        # On ne fait plus de sort_values() pour garder l'ordre du PDF.
            
        return df