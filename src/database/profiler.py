# src/database/profiler.py
"""Profilage automatique de la base SQLite : schéma, statistiques, valeurs réelles."""

import json
import sqlite3
from pathlib import Path

from src.database.connection import DatabaseConnection

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "elections.db"
PROFILE_PATH = PROJECT_ROOT / "data" / "processed" / "db_profile.json"

# Une colonne texte avec au plus ce nombre de valeurs distinctes est listée en entier.
MAX_CATEGORICAL = 40
SAMPLE_ROWS = 3
TOP_VALUES = 5


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _profile_column(conn: sqlite3.Connection, obj: str, col: str, col_type: str, total: int) -> dict:
    q_obj, q_col = _quote(obj), _quote(col)
    nulls, distinct = conn.execute(
        f"SELECT SUM({q_col} IS NULL), COUNT(DISTINCT {q_col}) FROM {q_obj}"
    ).fetchone()
    info = {
        "type": col_type or "TEXT",
        "null_pct": round(100 * (nulls or 0) / total, 1) if total else 0.0,
        "distinct": distinct,
    }

    # Les colonnes calculées d'une vue n'ont pas de type déclaré : on le déduit des données.
    actual = conn.execute(
        f"SELECT typeof({q_col}) FROM {q_obj} WHERE {q_col} IS NOT NULL LIMIT 1"
    ).fetchone()
    if actual and actual[0] in ("integer", "real"):
        info["type"] = col_type or actual[0].upper()
        is_numeric = True
    else:
        is_numeric = (col_type or "").upper() in ("INTEGER", "INT", "REAL", "FLOAT", "NUMERIC", "BOOL", "BOOLEAN")
    if is_numeric:
        lo, hi = conn.execute(f"SELECT MIN({q_col}), MAX({q_col}) FROM {q_obj}").fetchone()
        info["min"], info["max"] = lo, hi
    elif distinct and distinct <= MAX_CATEGORICAL:
        rows = conn.execute(
            f"SELECT DISTINCT {q_col} FROM {q_obj} WHERE {q_col} IS NOT NULL ORDER BY 1"
        ).fetchall()
        info["values"] = [r[0] for r in rows]
    elif distinct:
        rows = conn.execute(
            f"SELECT {q_col}, COUNT(*) c FROM {q_obj} WHERE {q_col} IS NOT NULL "
            f"GROUP BY {q_col} ORDER BY c DESC LIMIT {TOP_VALUES}"
        ).fetchall()
        info["top_values"] = [r[0] for r in rows]
    return info


def build_profile(db_path: Path = DB_PATH) -> dict:
    """Parcourt les tables et vues de la base et retourne son profil."""
    db = DatabaseConnection(db_path=str(db_path), read_only=True)
    profile: dict = {}
    with db.get_connection() as conn:
        objects = conn.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        for name, kind in objects:
            total = conn.execute(f"SELECT COUNT(*) FROM {_quote(name)}").fetchone()[0]
            cols = conn.execute(f"PRAGMA table_info({_quote(name)})").fetchall()
            fks = []
            if kind == "table":
                fks = [
                    f"{r[3]} -> {r[2]}.{r[4]}"
                    for r in conn.execute(f"PRAGMA foreign_key_list({_quote(name)})").fetchall()
                ]
            samples = [
                dict(r) for r in conn.execute(f"SELECT * FROM {_quote(name)} LIMIT {SAMPLE_ROWS}")
            ]
            profile[name] = {
                "kind": kind,
                "rows": total,
                "foreign_keys": fks,
                "columns": {c[1]: _profile_column(conn, name, c[1], c[2], total) for c in cols},
                "samples": samples,
            }
    return profile


def load_profile(refresh: bool = False) -> dict:
    """Charge le profil depuis le cache, ou le recalcule si absent/obsolète."""
    if (
        not refresh
        and PROFILE_PATH.exists()
        and DB_PATH.exists()
        and PROFILE_PATH.stat().st_mtime >= DB_PATH.stat().st_mtime
    ):
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile = build_profile()
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def _short(v, n: int = 60):
    return v[:n] + "…" if isinstance(v, str) and len(v) > n else v


def _describe_column(name: str, c: dict) -> str:
    parts = [f"{name} ({c['type']}"]
    if c["null_pct"]:
        parts[0] += f", {c['null_pct']}% NULL"
    parts[0] += ")"
    if "min" in c and c["min"] is not None:
        parts.append(f"[{c['min']} .. {c['max']}]")
    if "values" in c:
        parts.append("valeurs: " + ", ".join(repr(_short(v)) for v in c["values"]))
    elif "top_values" in c:
        parts.append(f"{c['distinct']} valeurs distinctes, ex: " + ", ".join(repr(_short(v)) for v in c["top_values"]))
    return " ".join(parts)


def format_profile_for_prompt(profile: dict, objects: list[str] | None = None) -> str:
    """Rend le profil en texte compact pour le prompt du LLM."""
    lines = []
    for name, p in profile.items():
        if objects is not None and name not in objects:
            continue
        lines.append(f"{p['kind'].upper()} {name} ({p['rows']} lignes)")
        for col, c in p["columns"].items():
            lines.append("  - " + _describe_column(col, c))
        for fk in p["foreign_keys"]:
            lines.append(f"  - clé étrangère : {fk}")
        if p["samples"]:
            lines.append("  exemples : " + json.dumps(p["samples"][:2], ensure_ascii=False))
        lines.append("")
    return "\n".join(lines).strip()


if __name__ == "__main__":
    prof = load_profile(refresh=True)
    print(format_profile_for_prompt(prof))
    print(f"\nProfil écrit dans {PROFILE_PATH}")
