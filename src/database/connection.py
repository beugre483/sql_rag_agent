# db/connection.py

import sqlite3
from pathlib import Path

class DatabaseConnection:
    """
    Fournisseur de connexion SQLite.
    Gère uniquement l'ouverture de la connexion (avec sécurité Read-Only si demandé).
    """

    def __init__(self, db_path: str = "elections.db", read_only: bool = True):
        """
        Args:
            db_path: Chemin vers le fichier .db
            read_only: Si True, la connexion sera verrouillée en lecture seule.
        """
        self.db_path = Path(db_path).resolve()
        self.read_only = read_only

        if not self.db_path.exists():
            print(f"⚠️ Attention : Le fichier base de données '{self.db_path.name}' n'existe pas encore.")

    def get_connection(self) -> sqlite3.Connection:
        """
        Crée et retourne l'objet connexion sqlite3.
        C'est à l'appelant de gérer les curseurs et la fermeture (avec 'with ...').
        """
        if self.read_only:
            # Mode URI pour forcer le Read-Only au niveau du driver
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        
        # Configuration pour récupérer les résultats comme des dictionnaires (accès par nom de colonne)
        conn.row_factory = sqlite3.Row
        
        return conn