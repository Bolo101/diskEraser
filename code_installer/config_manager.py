"""
config_manager.py – Gestion du mot de passe administrateur.
Stocke un hash PBKDF2-SHA256 + sel dans /etc/disk_eraser/admin.conf (root:root 600).
"""
import hashlib
import hmac
import json
import os
import secrets
import sys

CONFIG_DIR  = "/etc/disk_eraser"
CONFIG_FILE = os.path.join(CONFIG_DIR, "admin.conf")

# ── Dérivation de clé ──────────────────────────────────────────────────────────

def _derive(password: str, salt: str) -> str:
    """Retourne le hash PBKDF2-SHA256 en hexadécimal."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=200_000,
    )
    return key.hex()


# ── API publique ───────────────────────────────────────────────────────────────

def is_password_set() -> bool:
    """Vérifie qu'un mot de passe admin a déjà été configuré."""
    return os.path.isfile(CONFIG_FILE)


def set_password(password: str) -> None:
    """
    Enregistre (ou remplace) le mot de passe admin.
    Lève PermissionError si le répertoire n'est pas accessible en écriture.
    """
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")
    
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    salt   = secrets.token_hex(32)
    hashed = _derive(password, salt)
    
    payload = {"hash": hashed, "salt": salt}
    tmp = CONFIG_FILE + ".tmp"
    
    try:
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_FILE)     # atomic
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def verify_password(password: str) -> bool:
    """
    Vérifie si le mot de passe fourni correspond au hash enregistré.
    Retourne False en cas d'erreur de lecture (jamais d'exception).
    """
    if not os.path.isfile(CONFIG_FILE):
        return False
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        candidate = _derive(password, config["salt"])
        # Comparaison en temps constant (contre les attaques temporelles)
        return hmac.compare_digest(candidate, config["hash"])
    except (KeyError, json.JSONDecodeError, OSError, ValueError):
        return False


def change_password(old_password: str, new_password: str) -> None:
    """
    Change le mot de passe après vérification de l'ancien.
    Lève ValueError si l'ancien mot de passe est incorrect.
    """
    if not verify_password(old_password):
        raise ValueError("Ancien mot de passe incorrect.")
    set_password(new_password)