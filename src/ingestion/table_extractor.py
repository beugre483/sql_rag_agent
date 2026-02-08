import os
import pandas as pd
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from llama_cloud_services import LlamaExtract
from llama_cloud_services.extract import ExtractConfig, ExtractMode, ExtractTarget


class LigneResultat(BaseModel):
    # Infos Région/Circo (souvent fusionnées verticalement)
    region: Optional[str] = Field(default=None, description="Nom de la RÉGION (colonne gauche). Laisser null si vide/fusionné.")
    code_circo: Optional[str] = Field(default=None, description="Code numérique circonscription (ex: 001).")
    nom_circo: Optional[str] = Field(default=None, description="Nom de la circonscription (ex: AGBOVILLE). Ignorer le code.")
    
    # Stats Circo
    nb_bureaux: Optional[int] = Field(default=None, description="NB BV")
    inscrits: Optional[int] = Field(default=None, description="INSCRITS")
    votants: Optional[int] = Field(default=None, description="VOTANTS")
    taux_participation: Optional[float] = Field(default=None, description="TAUX DE PART (%)")
    bulletins_nuls: Optional[int] = Field(default=None, description="BULL. NULS")
    suffrages_exprimes: Optional[int] = Field(default=None, description="SUF. EXPRIMES")
    nb_blancs: Optional[int] = Field(default=None, description="BULL. BLANCS NOMBRE")
    pourcentage_blancs: Optional[float] = Field(default=None, description="BULL. BLANCS %")

    # Infos Candidat
    parti: Optional[str] = Field(default=None, description="GROUPEMENTS / PARTIS (ex: RHDP, INDEPENDANT, PPA-CI).")
    candidat: str = Field(description="CANDIDATS / LISTES DE CANDIDATS")
    score: int = Field(description="SCORES (Nombre de voix)")
    pourcentage: float = Field(description="% (Pourcentage voix)")
    est_elu: bool = Field(default=False, description="Mettre True si la colonne mentionne 'ELU'.")

    @field_validator('est_elu', mode='before')
    @classmethod
    def check_elu(cls, v):
        if isinstance(v, str):
            return "ELU" in v.upper()
        return bool(v)

class ResultatsElection(BaseModel):
    lignes: List[LigneResultat]

# --- EXTRACTEUR CORRIGÉ ---
class PDFElectionExtractor:
    def __init__(self, api_key: str):
        self.client = LlamaExtract(api_key=api_key)
        self.df_raw = pd.DataFrame()

    async def extract_from_pdf(self, pdf_path: str):
        """
        Extrait le PDF ligne par ligne en préservant l'ordre.
        """
        print(f"   ... Envoi du PDF à LlamaCloud ({pdf_path}) ...")
        

        config = ExtractConfig(
            extraction_mode=ExtractMode.PREMIUM,
            extraction_target=ExtractTarget.PER_TABLE_ROW,
            parse_model="anthropic-sonnet-4.5" 
        )
        
        try:
            response = await self.client.aextract(
                data_schema=ResultatsElection,
                files=[pdf_path],
                config=config
            )
            
            all_rows = []
            for page in response.data:
                if "lignes" in page:
                    all_rows.extend(page["lignes"])
            
            self.df_raw = pd.DataFrame(all_rows)
            return self.df_raw
            
        except Exception as e:
            print(f"ERREUR LlamaExtract : {e}")
            self.df_raw = pd.DataFrame()
            return self.df_raw

    def to_dataframe(self) -> pd.DataFrame:
        """
        Nettoie et propage les données (ffill).
        """
        if self.df_raw.empty:
            return pd.DataFrame()

        df = self.df_raw.copy()

        cols_to_fill = [
            'region', 'code_circo', 'nom_circo', 
            'nb_bureaux', 'inscrits', 'votants', 'taux_participation', 
            'bulletins_nuls', 'suffrages_exprimes', 'nb_blancs', 'pourcentage_blancs'
        ]
        
        # Convertir les vides/None en NaN pour que ffill fonctionne
        df[cols_to_fill] = df[cols_to_fill].replace('', pd.NA).replace('None', pd.NA)
        df[cols_to_fill] = df[cols_to_fill].ffill()

        # Nettoyage de sécurité
        df = df.dropna(subset=['region', 'candidat'])
        
        return df