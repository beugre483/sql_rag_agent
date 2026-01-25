"""
Extracteur de données électorales depuis PDF

Ce module fournit une classe pour extraire et normaliser les données
électorales .

"""

from pydantic import BaseModel, Field
from typing import List, Optional
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os 
from llama_cloud_services import LlamaExtract 
from llama_cloud_services.extract  import ExtractConfig,ExtractMode,ExtractTarget
load_dotenv()

# Récupère la clé
api_key = os.getenv("LLAMA_CLOUD_API_KEY")


#schemas pydantic qui servirons lors de l'extraction par notre modèle 
#il se servira des description de chaque fields pour l'extraction

class Candidat(BaseModel):
    """
    Représente un candidat ou une liste électorale.
    
    Attributes:
        parti_politique: Groupement politique (ex: RHDP, PDCI-RDA, INDEPENDANT)
        nom_liste_candidat: Nom du candidat ou de la liste
        score_voix: Nombre de voix obtenues (espaces retirés)
        pourcentage_voix: Pourcentage des voix (sans le symbole %)
        est_elu: True si marqué comme ELU(E), False sinon
    """
    parti_politique: str = Field(
        description="Le groupement ou parti politique (ex: RHDP, PDCI-RDA, INDEPENDANT). Si vide, laisser vide."
    )
    nom_liste_candidat: str = Field(
        description="Le nom du candidat ou de la liste de candidats."
    )
    score_voix: int = Field(
        description="Le nombre de voix (SCORE) obtenu. Ignorer les espaces (ex: '5 421' devient 5421)."
    )
    pourcentage_voix: float = Field(
        description="Le pourcentage (%) des voix. Exclure le signe %. (ex: '47,77%' devient 47.77)."
    )
    est_elu: bool = Field(
        description="Mettre True si la colonne mentionne 'ELU(E)', sinon False."
    )


class Circonscription(BaseModel):
    """
    Représente une circonscription électorale avec ses statistiques.
    
    Attributes:
        region_nom: Le nom de la RÉGION (Colonne 1, ex: AGNEBY-TIASSA). Si la cellule est vide/fusionnée, reprendre la valeur du bloc visuel parent.
         "IMPORTANT : Si la cellule est vide, c'est qu'elle appartient à la même région 
        Tu dois surtous pas oublier le nom de la region.
        code_circonscription: Code numérique (ex: 061, 062)
        nom_circonscription: Nom complet (ex: BOUNDA, BROBO)
        nb_bureaux_vote: Nombre de bureaux de vote
        inscrits: Nombre d'inscrits
        votants: Nombre de votants
        taux_participation: Taux de participation en décimal
        bulletins_nuls: Nombre de bulletins nuls
        suffrages_exprimes: Nombre de suffrages exprimés
        bulletins_blancs_nombre: Nombre de bulletins blancs
        bulletins_blancs_pourcentage: Pourcentage de bulletins blancs
        liste_candidats: Liste des candidats de cette circonscription
    """
    # Identification
    
    region_nom: Optional[str] = Field(
        description="Le nom de la RÉGION (Colonne 1, ex: AGNEBY-TIASSA). Si la cellule est vide/fusionnée, reprendre la valeur du bloc visuel parent."
        "IMPORTANT : Si la cellule est vide, c'est qu'elle appartient à la même région "
    )
    code_circonscription: str = Field(
        description="Le numéro/code à gauche du nom de la circonscription (ex: 061, 062)."
    )
    nom_circonscription: str = Field(
        description="Le nom complet de la circonscription (ex: BOUNDA, BROBO...)."
    )

    # Statistiques globales
    nb_bureaux_vote: int = Field(description="Colonne 'NB BV'")
    inscrits: int = Field(description="Colonne 'INSCRITS'")
    votants: int = Field(description="Colonne 'VOTANTS'")
    taux_participation: float = Field(
        description="Colonne 'TAUX DE PART.'. Convertir en décimal (ex: 40.36)."
    )
    bulletins_nuls: int = Field(description="Colonne 'BULL. NULS'")
    suffrages_exprimes: int = Field(description="Colonne 'SUF. EXPRIMES'")

    # Bulletins blancs (2 sous-colonnes)
    bulletins_blancs_nombre: int = Field(description="Colonne BULL. BLANCS -> NOMBRE")
    bulletins_blancs_pourcentage: float = Field(description="Colonne BULL. BLANCS -> %")

    # Relations
    liste_candidats: List[Candidat] = Field(
        description="Liste de tous les candidats alignés horizontalement avec cette circonscription (cellules fusionnées)."
    )


class ResultatsElection(BaseModel):
    """
    Schéma racine pour l'extraction des résultats électoraux.
      IMPORTANT:
    - La région (REGION) est souvent indiquée une seule fois en en-tête de bloc.
    - Si une circonscription ne contient pas explicitement le nom de la région,
      le modèle DOIT reprendre la dernière région détectée visuellement au-dessus.
    - Generatlement le nom de la region est renseigné pour un groupe de circonsription et sur la prémière colonne de facon centré
    
    Attributes:
        resultats: Liste de toutes les circonscriptions de la page
    """
    resultats: List[Circonscription] = Field(
        description="Liste de toutes les circonscriptions détectées sur la page."
    )


#Extracteur 

class PDFElectionExtractor:
    """
    Extracteur de données électorales depuis PDF.
    
    Cette classe gère l'extraction complète des données électorales :
    - Connexion à l'API LlamaExtract
    - Extraction  via Pydantic schemas
    - Nettoyage et normalisation des données
    - Export en DataFrame pandas

    """
    
    # Ordre des colonnes pour l'export final
    COLUMNS_ORDER = [
        "region_nom", "code_circonscription", "nom_circonscription",
        "nb_bureaux_vote", "inscrits", "votants", "taux_participation", 
        "bulletins_nuls", "suffrages_exprimes", 
        "bulletins_blancs_nombre", "bulletins_blancs_pourcentage",
        "parti_politique", "nom_liste_candidat", 
        "score_voix", "pourcentage_voix", "est_elu"
    ]
    
    def __init__(self, api: str):
        """
        Initialise l'extracteur.
        
        Args:
            api_key: Clé API pour LlamaExtract
        """
        self.llama_extract = LlamaExtract(api_key=api)
        self._raw_data = None
        self._df = None
    
    async def extract_from_pdf(self, pdf_path: str) -> List[dict]:
        """
        Extrait les données brutes du PDF via l'API.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            
        Returns:
            Liste de dictionnaires représentant les circonscriptions
            
        Raises:
            FileNotFoundError: Si le PDF n'existe pas
            ValueError: Si l'extraction échoue
        """
        # Vérifier l'existence du fichier
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"Le fichier {pdf_path} n'existe pas")
        
        print(f" Extraction du PDF : {pdf_path}")
        
        # Appel API avec configuration premium
        result = await self.llama_extract.aextract(
            data_schema=ResultatsElection,
            files=[pdf_path],
            config=ExtractConfig(
                extraction_mode=ExtractMode.PREMIUM,
                extraction_target=ExtractTarget.PER_TABLE_ROW,
                parse_model="anthropic-sonnet-4.5",
            ),
        )
        
        if not result:
            raise ValueError("L'extraction a échoué : aucun résultat retourné")
        
        # Extraction des données brutes
        donnees_brutes = result.data
        
        # Aplatissement : regrouper toutes les circonscriptions
        all_circonscriptions = []
        for page_data in donnees_brutes:
            if 'resultats' in page_data and isinstance(page_data['resultats'], list):
                all_circonscriptions.extend(page_data['resultats'])
        
        print(f" {len(all_circonscriptions)} circonscriptions extraites")
        
        self._raw_data = all_circonscriptions
        return all_circonscriptions
    
    def _flatten_to_dataframe(self, circonscriptions: List[dict]) -> pd.DataFrame:
        """
        Convertit les données hiérarchiques en DataFrame plat.
        
        Chaque ligne du DataFrame représente un candidat avec les infos
        de sa circonscription parente.
        
        Args:
            circonscriptions: Liste de dictionnaires de circonscriptions
            
        Returns:
            DataFrame pandas avec une ligne par candidat
        """
        print(f" Aplatissement de {len(circonscriptions)} circonscriptions...")
        
        data_flat = []
        
        for circo_dict in circonscriptions:
            # Conversion en objet Pydantic pour validation
            circo = Circonscription(**circo_dict)
            
            # Infos parentes (sans les enfants)
            info_parent = circo.model_dump(exclude={"liste_candidats"})
            
            # Pour chaque candidat, fusionner avec infos parent
            for candidat in circo.liste_candidats:
                info_enfant = candidat.model_dump()
                ligne_complete = {**info_parent, **info_enfant}
                data_flat.append(ligne_complete)
        
        df = pd.DataFrame(data_flat)
        
        # Réorganiser les colonnes selon l'ordre défini
        cols_existantes = [c for c in self.COLUMNS_ORDER if c in df.columns]
        df = df[cols_existantes]
        
        print(f" DataFrame créé : {len(df)} lignes × {len(df.columns)} colonnes")
        
        return df
    