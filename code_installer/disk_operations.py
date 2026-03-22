"""
disk_operations.py (installer) – Orchestration effacement / partition / formatage.
Identique au mode live mais enregistre chaque succès dans le compteur de supports.
"""
import re
import time
from subprocess import CalledProcessError

from disk_erase import erase_disk_crypto, erase_disk_hdd, get_disk_serial, is_ssd
from disk_format import format_disk
from disk_partition import partition_disk
from log_handler import log_error, log_info, log_erase_operation
from stats_manager import record_wipe
from utils import get_base_disk, get_physical_drives_for_logical_volumes, run_command


def process_disk(disk: str, fs_choice: str, passes: int,
                 use_crypto: bool = False, crypto_fill: str = "random",
                 log_func=None) -> None:
    """
    Efface, partitionne et formate un disque.
    Incrémente le compteur de supports blanchis en cas de succès.
    """
    def _log(msg: str) -> None:
        log_info(msg)
        if log_func:
            log_func(msg)

    try:
        disk_id = get_disk_serial(disk)
        _log(f"Traitement du disque : {disk_id}")

        if is_ssd(disk) and not use_crypto:
            _log(f"AVERTISSEMENT : {disk_id} est un SSD. "
                 "L'effacement multi-passes peut être insuffisant.")

        # ── Effacement ──
        if use_crypto:
            method_str = f"Effacement cryptographique ({crypto_fill})"
            _log(f"Méthode : {method_str}")
            erase_disk_crypto(disk, filling_method=crypto_fill, log_func=log_func)
        else:
            method_str = f"{passes} passe(s) d'écrasement"
            _log(f"Méthode : {method_str}")
            erase_disk_hdd(disk, passes, log_func=log_func)

        _log(f"Effacement terminé : {disk_id}")

        # ── Partitionnement ──
        _log(f"Création de la partition sur {disk_id}")
        partition_disk(disk)
        _log("Attente de reconnaissance de la partition…")
        time.sleep(5)

        # ── Formatage ──
        _log(f"Formatage de {disk_id} en {fs_choice}")
        format_disk(disk, fs_choice)

        # ── Journalisation opération ──
        log_erase_operation(disk_id, fs_choice, method_str)

        # ── Compteur ──
        count = record_wipe(disk_id, fs_choice, method_str)
        _log(f"✓ Disque {disk_id} traité avec succès. Total supports blanchis : {count}")

    except FileNotFoundError as e:
        log_error(f"Commande introuvable : {e}")
        if log_func:
            log_func(f"Commande introuvable : {e}")
        raise
    except CalledProcessError as e:
        log_error(f"Échec commande sur {disk} : {e}")
        if log_func:
            log_func(f"Échec commande sur {disk} : {e}")
        raise
    except PermissionError as e:
        log_error(f"Permission refusée pour {disk} : {e}")
        if log_func:
            log_func(f"Permission refusée pour {disk} : {e}")
        raise
    except OSError as e:
        log_error(f"Erreur OS pour {disk} : {e}")
        if log_func:
            log_func(f"Erreur OS pour {disk} : {e}")
        raise
    except KeyboardInterrupt:
        log_error(f"Traitement de {disk} interrompu par l'utilisateur.")
        if log_func:
            log_func(f"Traitement de {disk} interrompu.")
        raise


def get_active_disk():
    """
    Détecte le(s) disque(s) physique(s) hébergeant le système de fichiers racine.
    Retourne une liste de noms de base (ex. ['nvme0n1', 'sda']) ou None.
    """
    try:
        devices = set()

        with open("/proc/mounts", "r") as f:
            mounts_content = f.read()

        root_device = None
        for line in mounts_content.split("\n"):
            if " / " in line and line.strip():
                root_device = line.split()[0]
                break

        if not root_device or root_device in ("rootfs", "overlay", "aufs", "/dev/root"):
            # Live boot – cherche le média de boot dans les montages
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    device, mp = parts[0], parts[1]
                    if any(k in mp for k in ("/run/live", "/lib/live", "/live/", "/cdrom")):
                        m = re.search(r"/dev/([a-zA-Z]+\d*[a-zA-Z]*\d*)", device)
                        if m:
                            devices.add(get_base_disk(m.group(1)))
        else:
            if "/dev/mapper/" in root_device or "/dev/dm-" in root_device:
                for drive in get_physical_drives_for_logical_volumes([root_device]):
                    devices.add(get_base_disk(drive))
            else:
                m = re.search(r"/dev/([a-zA-Z]+\d*[a-zA-Z]*\d*)", root_device)
                if m:
                    devices.add(get_base_disk(m.group(1)))

        return list(devices) if devices else None

    except (OSError, ValueError, re.error) as e:
        log_error(f"Erreur détection disque actif : {e}")
        return None