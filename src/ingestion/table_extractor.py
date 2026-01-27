"""
Extracteur de données électorales depuis PDF - VERSION SÉCURISÉE

Corrections apportées :
1. Pas de propagation automatique dangereuse
2. Instructions ultra-précises sur les cellules fusionnées verticalement
3. Le modèle doit DÉTECTER visuellement la fusion de cellule
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os 
from llama_cloud_services import LlamaExtract 
from llama_cloud_services.extract import ExtractConfig, ExtractMode, ExtractTarget

load_dotenv()
api_key = os.getenv("LLAMA_CLOUD_API_KEY")


class Candidat(BaseModel):
    """
    Représente un candidat ou une liste électorale.
    """
    parti_politique: str = Field(
        description="Le groupement ou parti politique (ex: RHDP, PDCI-RDA, INDEPENDANT, ADCI, FPI, MGC). "
        "Si vide ou non renseigné, mettre 'NON RENSEIGNÉ'."
    )
    nom_liste_candidat: str = Field(
        description="Le nom du candidat ou de la liste de candidats. Ne jamais laisser vide."
    )
    score_voix: int = Field(
        description="Le nombre de voix (SCORE) obtenu. Retirer tous les espaces (ex: '5 421' → 5421)."
    )
    pourcentage_voix: float = Field(
        description="Le pourcentage (%) des voix. Retirer le symbole % (ex: '47,77%' → 47.77). "
        "Remplacer les virgules par des points."
    )
    est_elu: bool = Field(
        default=False,
        description="Mettre True uniquement si la colonne mentionne explicitement 'ELU(E)', sinon False."
    )


class Circonscription(BaseModel):
    """
    Représente une circonscription électorale avec ses statistiques.
    
    STRUCTURE RÉELLE DU TABLEAU - DESCRIPTION LITTÉRALE :
    
    Le tableau électoral contient plusieurs colonnes disposées horizontalement de gauche à droite.
    
    PREMIÈRE COLONNE à gauche : Elle a le header "RÉGION" écrit en haut. Cette colonne contient des noms de régions comme "AGNEBY-TIASSA", "ABIDJAN", "BELIER". Le texte de région est souvent écrit verticalement et la cellule est fusionnée sur plusieurs lignes consécutives. Par exemple, "AGNEBY-TIASSA" peut être écrit verticalement dans une grande cellule qui couvre les lignes 001, 002 et 003.
    
    DEUXIÈME COLONNE (ATTENTION PIÈGE) : Cette colonne N'A PAS de header en haut. C'est une colonne étroite qui contient uniquement des nombres à trois chiffres comme 001, 002, 003, 073, 074, 075, etc. Chaque ligne du tableau a son propre code unique dans cette colonne. Cette colonne est positionnée ENTRE la colonne RÉGION (à sa gauche) et la colonne CIRCONSCRIPTION (à sa droite).
    
    TROISIÈME COLONNE : Elle a le header "CIRCONSCRIPTION" écrit en haut. Cette colonne contient les noms longs des circonscriptions comme "ABOUDE, ATTOBROU, GUESSIGUIE, GRAND-MORIE, LOVIGUIE, ORESS-KROBOU, COMMUNES ET SOUS-PREFECTURES, AGBOVILLE SOUS-PREFECTURE" ou "AGBOVILLE COMMUNE" ou "AZAGUIE COMMUNE ET SOUS-PREFECTURE".
    
    COLONNES SUIVANTES : Après ces trois premières colonnes, il y a d'autres colonnes avec les headers "NB BV", "INSCRITS", "VOTANTS", "TAUX DE PART.", "BULL. NULS", "SUF. EXPRIMES", "BULL. BLANCS", etc.
    
    RÈGLES D'EXTRACTION PAR COLONNE :
    
    PREMIÈRE COLONNE (header "RÉGION") :
       - Contient du TEXTE écrit VERTICALEMENT comme "AGNEBY-TIASSA", "ABIDJAN", "BELIER"
       - Une cellule fusionnée verticalement couvre plusieurs lignes
       - Pour extraire : identifier visuellement dans quelle cellule fusionnée se trouve la ligne actuelle
       - Extraire le texte de cette cellule fusionnée
       - Cette valeur va dans le champ region_nom
       - Si invisible ou vide : mettre "RÉGION_À_VÉRIFIER"
    
    DEUXIÈME COLONNE (SANS header - colonne étroite entre RÉGION et CIRCONSCRIPTION) :
       - Contient les CODES NUMÉRIQUES : 001, 002, 003, 073, 074, etc.
       - C'est une petite colonne étroite
       - TOUJOURS un nombre à 3 chiffres
       - Cette valeur va dans le champ code_circonscription
       - Si invisible : mettre "999" (jamais de texte)
    
    TROISIÈME COLONNE (header "CIRCONSCRIPTION") :
       - Contient le nom complet comme "ABOUDE, ATTOBROU...", "AGBOVILLE COMMUNE"
       - Cette valeur va dans le champ nom_circonscription
    
    COLONNES SUIVANTES :
       - Contiennent les statistiques : NB BV, INSCRITS, VOTANTS, TAUX DE PART., etc.
    
    PIÈGE PRINCIPAL : La deuxième colonne (celle avec les codes 001, 002, 003...) n'a PAS de header visible en haut du tableau. C'est une petite colonne étroite située ENTRE la colonne RÉGION et la colonne CIRCONSCRIPTION.
    """
    
    region_nom: str = Field(
        description=(
            "NOM DE LA RÉGION - C'est la valeur de la PREMIÈRE colonne du tableau (celle qui est tout à gauche).\n"
            "\n"
            "Cette première colonne a le header RÉGION écrit en haut. Elle contient des noms de régions écrits en texte, souvent de manière verticale sur plusieurs lignes.\n"
            "\n"
            "Exemples de valeurs correctes pour region_nom : AGNEBY-TIASSA, ABIDJAN, BELIER, CAVALLY, GBOKLE, INDENIE-DJUABLIN, GRANDS PONTS.\n"
            "\n"
            "RÈGLE CRITIQUE SUR LES CELLULES FUSIONNÉES : Une cellule de région est fusionnée verticalement et couvre TOUTES les lignes de circonscriptions qui appartiennent à cette région. La fusion commence dès la PREMIÈRE ligne de la région.\n"
            "\n"
            "EXEMPLE CONCRET AVEC AGNEBY-TIASSA : Si tu vois une grande cellule avec AGNEBY-TIASSA écrit verticalement, cette cellule couvre les lignes 001, 002 et 003 SIMULTANÉMENT. Cela signifie que :\n"
            "- Ligne 001 avec ABOUDE ATTOBROU a pour région AGNEBY-TIASSA\n"
            "- Ligne 002 avec AGBOVILLE COMMUNE a pour région AGNEBY-TIASSA\n"
            "- Ligne 003 avec AZAGUIE COMMUNE a pour région AGNEBY-TIASSA\n"
            "\n"
            "La cellule fusionnée ne commence pas à la ligne 002 ou 003, elle commence à la ligne 001 et englobe toutes ces lignes.\n"
            "\n"
            "EXEMPLE CONCRET AVEC GRANDS PONTS : Si tu vois GRANDS PONTS écrit verticalement dans une cellule fusionnée, cette cellule peut couvrir plusieurs lignes consécutives (par exemple lignes 073, 074, 075, 076). Toutes ces lignes ont GRANDS PONTS comme région.\n"
            "\n"
            "Méthode d'extraction : Pour la ligne actuelle, regarde la première colonne à gauche. Identifie dans quelle cellule fusionnée se trouve cette ligne. Lis le texte écrit dans cette cellule fusionnée. Ce texte est la région, même si c'est la première ligne du bloc.\n"
            "\n"
            "NE PAS CONFONDRE region_nom avec : les codes numériques 001, 073, 074 (qui sont dans la deuxième colonne), ni avec les noms de circonscriptions comme ABOUDE ATTOBROU ou AGBOVILLE COMMUNE (qui sont dans la troisième colonne).\n"
            "\n"
            "Si la région n'est vraiment pas visible ou ambiguë : mettre RÉGION_À_VÉRIFIER. Mais dans la plupart des cas, la région est visible dans la cellule fusionnée qui couvre la ligne actuelle."
        )
    )
    
    code_circonscription: str = Field(
        description=(
            "CODE NUMÉRIQUE - C'est la valeur de la DEUXIÈME colonne du tableau.\n"
            "\n"
            "ATTENTION RÈGLE CRITIQUE : Cette deuxième colonne N'A PAS de header visible en haut du tableau. C'est une colonne étroite sans titre qui se trouve ENTRE la colonne RÉGION (à sa gauche) et la colonne CIRCONSCRIPTION (à sa droite).\n"
            "\n"
            "Cette colonne contient TOUJOURS un nombre à trois chiffres UNIQUE pour chaque ligne. Les codes vont de 001 jusqu'à 164 environ (chaque circonscription a son propre numéro séquentiel).\n"
            "\n"
            "Exemples concrets de ce que tu dois voir dans cette colonne : Sur la ligne avec ABOUDE ATTOBROU tu verras 001, sur la ligne avec AGBOVILLE COMMUNE tu verras 002, sur la ligne avec AZAGUIE tu verras 003, etc. Plus loin dans le tableau tu verras 073, 074, 075, et ainsi de suite jusqu'à environ 164.\n"
            "\n"
            "COMMENT TROUVER CETTE COLONNE : Regarde entre la première colonne (celle avec les noms de régions comme AGNEBY-TIASSA ou GRANDS PONTS écrits verticalement) et la troisième colonne (celle avec les longs noms de circonscriptions comme ABOUDE ATTOBROU ou AHOUANOU BACANDA EBONOU). Entre ces deux colonnes, il y a une PETITE colonne étroite qui contient juste des nombres. Cette petite colonne est le code_circonscription.\n"
            "\n"
            "IMPORTANT : Chaque ligne du tableau a son PROPRE code DIFFÉRENT. Si tu vois plusieurs lignes avec GRANDS PONTS comme région, elles auront des codes DIFFÉRENTS (par exemple une ligne aura 073, une autre 074, une autre 075, etc). NE METS PAS 999 sauf si cette petite colonne est vraiment complètement invisible ou illisible.\n"
            "\n"
            "Le code 999 est une valeur d'URGENCE à utiliser UNIQUEMENT si la petite colonne des codes est totalement absente ou illisible. Dans 99 pourcent des cas, le vrai code numérique est présent dans la petite colonne étroite entre RÉGION et CIRCONSCRIPTION.\n"
            "\n"
            "Méthode d'extraction pas à pas : Pour la ligne actuelle, localise d'abord la colonne RÉGION à gauche (avec un nom comme AGNEBY-TIASSA). Localise ensuite la colonne CIRCONSCRIPTION plus à droite (avec un long nom comme ABOUDE ATTOBROU GUESSIGUIE). Regarde maintenant ENTRE ces deux colonnes. Il y a une petite colonne étroite. Lis le nombre qui se trouve dans cette petite colonne sur la ligne actuelle. Ce nombre est le code_circonscription. Chaque ligne a un nombre différent dans cette colonne."
        )
    )
    
    nom_circonscription: str = Field(
        description=(
            "NOM COMPLET de la circonscription - C'est la valeur de la TROISIÈME colonne du tableau.\n"
            "\n"
            "Cette troisième colonne a le header CIRCONSCRIPTION écrit en haut. Elle se trouve à droite de la petite colonne des codes numériques.\n"
            "\n"
            "Exemples de valeurs correctes pour nom_circonscription : ABOUDE ATTOBROU GUESSIGUIE GRAND-MORIE LOVIGUIE ORESS-KROBOU COMMUNES ET SOUS-PREFECTURES AGBOVILLE SOUS-PREFECTURE, ou AGBOVILLE COMMUNE, ou AZAGUIE COMMUNE ET SOUS-PREFECTURE.\n"
            "\n"
            "NE PAS CONFONDRE nom_circonscription avec : la région de la première colonne (comme AGNEBY-TIASSA), ni avec le code numérique de la deuxième colonne (comme 001, 002, 073)."
        )
    )

    # Statistiques globales
    nb_bureaux_vote: int = Field(description="Colonne 'NB BV' - nombre de bureaux de vote")
    inscrits: int = Field(description="Colonne 'INSCRITS' - retirer les espaces")
    votants: int = Field(description="Colonne 'VOTANTS' - retirer les espaces")
    
    taux_participation: float = Field(
        description="Colonne 'TAUX DE PART.' - convertir en décimal (ex: '27,00%' → 27.00)"
    )
    
    bulletins_nuls: int = Field(description="Colonne 'BULL. NULS' - retirer les espaces")
    suffrages_exprimes: int = Field(description="Colonne 'SUF. EXPRIMES' - retirer les espaces")

    # Bulletins blancs (2 sous-colonnes)
    bulletins_blancs_nombre: int = Field(
        description="Sous-colonne 'BULL. BLANCS' → 'NOMBRE'"
    )
    bulletins_blancs_pourcentage: float = Field(
        description="Sous-colonne 'BULL. BLANCS' → '%' (retirer le symbole %)"
    )

    # Relations
    liste_candidats: List[Candidat] = Field(
        description=(
            "Liste de TOUS les candidats/partis listés horizontalement à droite de cette circonscription. "
            "Chaque parti a une colonne : GROUPEMENT POLITIQUE, puis les résultats en dessous."
        )
    )
    
    @field_validator('code_circonscription')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """
        Validation stricte : le code doit être numérique et pas 999 sauf exception
        """
        v_clean = v.strip()
        
        # Rejeter les valeurs textuelles
        if v_clean in ['RÉGION_À_VÉRIFIER', 'NON RENSEIGNÉ', '']:
            raise ValueError(
                f"ERREUR CRITIQUE : code_circonscription='{v_clean}' n'est PAS un nombre. "
                "Le code_circonscription est dans la petite colonne étroite ENTRE la colonne RÉGION et la colonne CIRCONSCRIPTION. "
                "C'est TOUJOURS un nombre à 3 chiffres comme 001, 073, 164. "
                "Cherche la petite colonne sans header entre RÉGION et CIRCONSCRIPTION."
            )
        
        if not v_clean.isdigit():
            raise ValueError(
                f"ERREUR : code_circonscription='{v_clean}' doit être un NOMBRE à 3 chiffres. "
                "Exemples valides : 001, 073, 164. "
                "Tu dois lire la petite colonne étroite entre RÉGION et CIRCONSCRIPTION."
            )
        
        # Warning si trop de 999 (signe que le modèle ne trouve pas la vraie colonne)
        if v_clean == '999':
            import warnings
            warnings.warn(
                f"ATTENTION : code_circonscription=999 détecté. Es-tu sûr que la petite colonne des codes "
                "est invisible ? Cherche bien la colonne étroite ENTRE RÉGION et CIRCONSCRIPTION. "
                "Chaque ligne doit avoir son propre code unique (001, 002, 073, 074, etc)."
            )
        
        # Formater avec zéros de tête si nécessaire
        return v_clean.zfill(3)
    
    @field_validator('region_nom')
    @classmethod
    def validate_region(cls, v: str) -> str:
        """
        Validation stricte : refuser les codes numériques dans region_nom
        """
        v_clean = v.strip().upper()
        
        if v_clean.isdigit():
            raise ValueError(
                f" ERREUR : region_nom='{v_clean}' est un NOMBRE ! "
                "Les régions sont des NOMS (ex: 'AGNEBY-TIASSA', 'ABIDJAN'...), pas des codes. "
                "Tu as probablement confondu avec code_circonscription."
            )
        
        if not v_clean:
            return "RÉGION_VIDE"
        
        return v_clean


class ResultatsElection(BaseModel):
    """
    Schéma racine pour l'extraction des résultats électoraux.
    
    MÉTHODE D'EXTRACTION LIGNE PAR LIGNE :
    
    Le tableau électoral contient plusieurs lignes. Chaque ligne représente une circonscription. Pour chaque ligne du tableau, il faut extraire une circonscription complète avec toutes ses données.
    
    ÉTAPE PAR ÉTAPE pour extraire une ligne :
    
    PREMIÈRE ÉTAPE - Extraire region_nom depuis la première colonne :
    Regarder la première colonne du tableau (celle tout à gauche avec le header RÉGION). Identifier visuellement dans quelle cellule fusionnée se trouve la ligne actuelle. Cette cellule fusionnée peut couvrir plusieurs lignes consécutives. Lis le texte écrit dans cette cellule fusionnée. Ce texte est un nom de région comme AGNEBY-TIASSA ou ABIDJAN ou GRANDS PONTS. La cellule fusionnée couvre la ligne actuelle MÊME SI c'est la première ligne du bloc. Par exemple, si AGNEBY-TIASSA est dans une cellule qui couvre les lignes 001, 002 et 003, alors la ligne 001 a AGNEBY-TIASSA comme région (pas RÉGION_À_VÉRIFIER). Si la région n'est vraiment pas visible, mettre RÉGION_À_VÉRIFIER. Ce texte va dans le champ region_nom.
    
    DEUXIÈME ÉTAPE - Extraire code_circonscription depuis la deuxième colonne :
    Regarder la deuxième colonne du tableau (la petite colonne étroite SANS header qui se trouve entre RÉGION et CIRCONSCRIPTION). Cette colonne contient un nombre à trois chiffres comme 001, 002, 073, 074. Lire ce nombre. Ce nombre va dans le champ code_circonscription. Si le code n'est pas visible, mettre 999. IMPORTANT : Ce champ doit toujours contenir un nombre, jamais du texte comme RÉGION_À_VÉRIFIER.
    
    TROISIÈME ÉTAPE - Extraire nom_circonscription depuis la troisième colonne :
    Regarder la troisième colonne du tableau (celle avec le header CIRCONSCRIPTION). Extraire le texte de cette colonne. Ce texte peut être long comme ABOUDE ATTOBROU GUESSIGUIE GRAND-MORIE ou court comme AGBOVILLE COMMUNE. Ce texte va dans le champ nom_circonscription.
    
    QUATRIÈME ÉTAPE - Extraire les statistiques depuis les colonnes suivantes :
    Après les trois premières colonnes, il y a d'autres colonnes avec les headers NB BV, INSCRITS, VOTANTS, TAUX DE PART., BULL. NULS, SUF. EXPRIMES, BULL. BLANCS. Extraire les valeurs de ces colonnes pour la ligne actuelle.
    
    CINQUIÈME ÉTAPE - Extraire liste_candidats depuis les colonnes de droite :
    À droite du tableau, il y a plusieurs colonnes pour les différents partis politiques et candidats. Extraire tous les candidats listés horizontalement pour cette ligne.
    
    RÉPÉTER CES ÉTAPES pour chaque ligne du tableau afin de créer un objet Circonscription par ligne.
    
    RÈGLES CRITIQUES :
    - region_nom est toujours du TEXTE (comme AGNEBY-TIASSA), jamais un nombre.
    - code_circonscription est toujours un NOMBRE (comme 001, 073), jamais du texte.
    - nom_circonscription est toujours du TEXTE (comme AGBOVILLE COMMUNE).
    - Ne jamais mettre RÉGION_À_VÉRIFIER dans code_circonscription.
    - Chaque ligne du tableau produit une circonscription complète.
    """
    
    resultats: List[Circonscription] = Field(
        description=(
            "Liste de toutes les circonscriptions détectées sur la page. "
            "Pour chaque ligne du tableau, créer un objet Circonscription avec : "
            "region_nom depuis la première colonne (TEXTE comme AGNEBY-TIASSA), "
            "code_circonscription depuis la deuxième colonne sans header (NOMBRE comme 001 ou 073), "
            "nom_circonscription depuis la troisième colonne (TEXTE comme AGBOVILLE COMMUNE), "
            "et toutes les statistiques et candidats depuis les colonnes suivantes."
        )
    )


class PDFElectionExtractor:
    """
    Extracteur de données électorales depuis PDF.
    
    Version sécurisée : pas de propagation automatique dangereuse.
    """
    
    COLUMNS_ORDER = [
        "region_nom", "code_circonscription", "nom_circonscription",
        "nb_bureaux_vote", "inscrits", "votants", "taux_participation", 
        "bulletins_nuls", "suffrages_exprimes", 
        "bulletins_blancs_nombre", "bulletins_blancs_pourcentage",
        "parti_politique", "nom_liste_candidat", 
        "score_voix", "pourcentage_voix", "est_elu"
    ]
    
    def __init__(self, api: str):
        self.llama_extract = LlamaExtract(api_key=api)
        self._raw_data = None
        self._df = None
    
    async def extract_from_pdf(self, pdf_path: str) -> List[dict]:
        """
        Extrait les données brutes du PDF via l'API.
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"Le fichier {pdf_path} n'existe pas")
        
        print(f" Extraction du PDF : {pdf_path}")
        
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
        
        donnees_brutes = result.data
        
        # Aplatissement
        all_circonscriptions = []
        for page_data in donnees_brutes:
            if 'resultats' in page_data and isinstance(page_data['resultats'], list):
                all_circonscriptions.extend(page_data['resultats'])
        
        self._report_missing_regions(all_circonscriptions)
        
        print(f"{len(all_circonscriptions)} circonscriptions extraites")
        
        self._raw_data = all_circonscriptions
        return all_circonscriptions
    
    def _report_missing_regions(self, circonscriptions: List[dict]):
        """
        Génère un rapport sur les régions manquantes SANS les modifier.
        """
        missing = []
        for circo in circonscriptions:
            region = circo.get('region_nom', '').strip()
            code = circo.get('code_circonscription', '?')
            
            if not region or region in ['RÉGION_VIDE', 'RÉGION_À_VÉRIFIER']:
                missing.append(f"   Ligne {code} : région non détectée ('{region}')")
        
        if missing:
            print("\n RÉGIONS À VÉRIFIER MANUELLEMENT :")
            for msg in missing:
                print(msg)
            print("Conseil : Vérifier visuellement le PDF pour ces lignes\n")
    
    def _flatten_to_dataframe(self, circonscriptions: List[dict]) -> pd.DataFrame:
        """
        Convertit les données hiérarchiques en DataFrame plat.
        """
        print(f"Aplatissement de {len(circonscriptions)} circonscriptions...")
        
        data_flat = []
        
        for circo_dict in circonscriptions:
            # Validation Pydantic
            circo = Circonscription(**circo_dict)
            
            info_parent = circo.model_dump(exclude={"liste_candidats"})
            
            for candidat in circo.liste_candidats:
                info_enfant = candidat.model_dump()
                ligne_complete = {**info_parent, **info_enfant}
                data_flat.append(ligne_complete)
        
        df = pd.DataFrame(data_flat)
        
        # Réorganisation des colonnes
        cols_existantes = [c for c in self.COLUMNS_ORDER if c in df.columns]
        df = df[cols_existantes]
        
        print(f"DataFrame créé : {len(df)} lignes × {len(df.columns)} colonnes")
        
        return df
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convertit les données extraites en DataFrame.
        """
        if self._raw_data is None:
            raise ValueError("Aucune donnée extraite. Appelez d'abord extract_from_pdf()")
        
        self._df = self._flatten_to_dataframe(self._raw_data)
        return self._df
    
    def save_to_csv(self, output_path: str):
        """
        Sauvegarde le DataFrame en CSV.
        """
        if self._df is None:
            raise ValueError("Aucun DataFrame disponible. Appelez d'abord to_dataframe()")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"Fichier sauvegardé : {output_path}")
    
    def manual_region_fix(self, code_circonscription: str, correct_region: str):
        """
         Permet de corriger manuellement une région après extraction.
        
        Usage:
            extractor.manual_region_fix('001', 'AGNEBY-TIASSA')
            extractor.manual_region_fix('002', 'AGNEBY-TIASSA')
        """
        if self._raw_data is None:
            raise ValueError("Aucune donnée à corriger")
        
        for circo in self._raw_data:
            if circo.get('code_circonscription') == code_circonscription:
                old = circo.get('region_nom', 'N/A')
                circo['region_nom'] = correct_region
                print(f" Correction : Ligne {code_circonscription} : '{old}' → '{correct_region}'")
                return
        
        print(f" Code {code_circonscription} non trouvé")
    
    def get_regions_summary(self) -> pd.DataFrame:
        """
         Résumé des régions extraites pour vérification rapide.
        """
        if self._raw_data is None:
            raise ValueError("Aucune donnée extraite")
        
        summary = []
        for circo in self._raw_data:
            summary.append({
                'code': circo.get('code_circonscription'),
                'nom': circo.get('nom_circonscription', '')[:30],
                'region': circo.get('region_nom')
            })
        
        return pd.DataFrame(summary)