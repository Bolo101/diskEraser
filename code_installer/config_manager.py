"""
config_manager.py – Gestion du mot de passe administrateur et des paramètres.
Stocke un hash PBKDF2-SHA256 + sel + paramètres dans /etc/disk_eraser/admin.conf (root:root 600).
"""
import hashlib
import hmac
import json
import os
import secrets
import sys

CONFIG_DIR  = "/etc/disk_eraser"
CONFIG_FILE = os.path.join(CONFIG_DIR, "admin.conf")

DEFAULT_PASSES = 5

# ── Helpers internes ───────────────────────────────────────────────────────────

def _read_config() -> dict:
    """Lit le fichier de configuration, retourne un dict vide si absent ou illisible."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _write_config(data: dict) -> None:
    """Écrit le fichier de configuration de façon atomique."""
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_FILE)     # atomic
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


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


# ── API mot de passe ───────────────────────────────────────────────────────────

def is_password_set() -> bool:
    """Vérifie qu'un mot de passe admin a déjà été configuré."""
    config = _read_config()
    return "hash" in config and "salt" in config


def set_password(password: str) -> None:
    """
    Enregistre (ou remplace) le mot de passe admin.
    Préserve les autres paramètres existants (ex. nombre de passes).
    Lève PermissionError si le répertoire n'est pas accessible en écriture.
    """
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")

    salt   = secrets.token_hex(32)
    hashed = _derive(password, salt)

    # Fusion : on préserve les clés existantes (passes, etc.)
    config = _read_config()
    config["hash"] = hashed
    config["salt"] = salt
    _write_config(config)


def verify_password(password: str) -> bool:
    """
    Vérifie si le mot de passe fourni correspond au hash enregistré.
    Retourne False en cas d'erreur de lecture (jamais d'exception).
    """
    config = _read_config()
    if "hash" not in config or "salt" not in config:
        return False
    try:
        candidate = _derive(password, config["salt"])
        # Comparaison en temps constant (contre les attaques temporelles)
        return hmac.compare_digest(candidate, config["hash"])
    except (KeyError, ValueError):
        return False


def change_password(old_password: str, new_password: str) -> None:
    """
    Change le mot de passe après vérification de l'ancien.
    Lève ValueError si l'ancien mot de passe est incorrect.
    """
    if not verify_password(old_password):
        raise ValueError("Ancien mot de passe incorrect.")
    set_password(new_password)


# ── API paramètres d'effacement ────────────────────────────────────────────────

def get_passes() -> int:
    """
    Retourne le nombre de passes configuré (défaut : DEFAULT_PASSES).
    Ne lève jamais d'exception.
    """
    config = _read_config()
    try:
        return max(1, int(config.get("passes", DEFAULT_PASSES)))
    except (ValueError, TypeError):
        return DEFAULT_PASSES


def set_passes(passes: int) -> None:
    """
    Enregistre le nombre de passes.
    Lève ValueError si la valeur est invalide (< 1).
    Lève PermissionError si le fichier n'est pas accessible en écriture.
    """
    if not isinstance(passes, int) or passes < 1:
        raise ValueError("Le nombre de passes doit être un entier supérieur ou égal à 1.")
    config = _read_config()
    config["passes"] = passes
    _write_config(config)