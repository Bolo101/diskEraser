"""
stats_manager.py – Compteur persistant de supports blanchis.
Stocké dans /var/lib/disk_eraser/stats.json.
"""
import json
import logging
import os

STATS_DIR  = "/var/lib/disk_eraser"
STATS_FILE = os.path.join(STATS_DIR, "stats.json")

logger = logging.getLogger(__name__)


def _load() -> dict:
    """Charge le fichier stats ou retourne des valeurs par défaut."""
    if not os.path.isfile(STATS_FILE):
        return {"wipe_count": 0, "wipe_history": []}
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        # Compat descendante
        if "wipe_count" not in data:
            data["wipe_count"] = 0
        if "wipe_history" not in data:
            data["wipe_history"] = []
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Erreur lecture stats: {e}")
        return {"wipe_count": 0, "wipe_history": []}


def _save(data: dict) -> None:
    """Enregistre atomiquement les stats."""
    os.makedirs(STATS_DIR, mode=0o700, exist_ok=True)
    tmp = STATS_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STATS_FILE)
    except OSError as e:
        logger.error(f"Erreur écriture stats: {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass


# ── API publique ───────────────────────────────────────────────────────────────

def get_wipe_count() -> int:
    """Retourne le nombre total de supports blanchis."""
    return _load().get("wipe_count", 0)


def get_history() -> list:
    """Retourne l'historique des blanchiments sous forme de liste de dicts."""
    return _load().get("wipe_history", [])


def record_wipe(disk_id: str, filesystem: str, method: str) -> int:
    """
    Enregistre un blanchiment réussi.
    Retourne le nouveau compteur total.
    """
    from datetime import datetime
    
    data = _load()
    data["wipe_count"] = data.get("wipe_count", 0) + 1
    
    entry = {
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "disk_id":    disk_id,
        "filesystem": filesystem,
        "method":     method,
        "count_at":   data["wipe_count"],
    }
    data.setdefault("wipe_history", []).append(entry)
    
    _save(data)
    logger.info(f"Support blanchi #{data['wipe_count']} – {disk_id}")
    return data["wipe_count"]


def reset_counter() -> None:
    """Remet le compteur à zéro (réservé à l'interface admin)."""
    data = _load()
    data["wipe_count"]   = 0
    data["wipe_history"] = []
    _save(data)
    logger.info("Compteur de supports blanchis remis à zéro par l'administrateur.")