import logging
from utils import run_command
from subprocess import CalledProcessError
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Limites de longueur par système de fichiers
_LABEL_MAX = {"ntfs": 32, "ext4": 16, "vfat": 11}


def _sanitize_label(label: str, fs_choice: str) -> str:
    """Nettoie et tronque le libellé selon les contraintes du FS."""
    if not label:
        return ""
    label = label.strip()
    max_len = _LABEL_MAX.get(fs_choice, 16)
    return label[:max_len]


def apply_disk_label(partition: str, fs_choice: str, label: str) -> None:
    """
    Fallback : applique un libellé via les outils dédiés (e2label, ntfslabel, fatlabel).
    Utilisé uniquement si le label n'a pas pu être intégré au mkfs.
    Ne lève pas d'exception en cas d'échec (avertissement seulement).
    """
    label = _sanitize_label(label, fs_choice)
    if not label:
        return
    try:
        if fs_choice == "ntfs":
            run_command(["ntfslabel", partition, label])
        elif fs_choice == "ext4":
            run_command(["e2label", partition, label])
        elif fs_choice == "vfat":
            run_command(["fatlabel", partition, label])
        logging.info(f"Libellé (fallback) '{label}' appliqué sur {partition}")
    except FileNotFoundError:
        logging.warning(f"Outil d'étiquetage introuvable pour {fs_choice}, libellé ignoré.")
    except CalledProcessError as e:
        logging.warning(f"Impossible d'appliquer le libellé sur {partition} : {e}")


def format_disk(disk: str, fs_choice: str, label: str = None) -> None:
    """
    Formate une partition avec le système de fichiers choisi.
    Gère les nommages NVMe et disques standards.
    Le libellé est passé directement à la commande mkfs (option native) ;
    un fallback via les outils dédiés est tenté en cas d'échec.
    """
    disk_name = disk.replace('/dev/', '')

    from disk_partition import get_partition_name
    partition_name = get_partition_name(disk_name)
    partition = f"/dev/{partition_name}"

    logging.info(f"Attente de reconnaissance de la partition {partition}…")
    time.sleep(2)

    lbl = _sanitize_label(label or "", fs_choice)
    label_applied_via_mkfs = False

    try:
        if fs_choice == "ntfs":
            logging.info(f"Formatage {partition} en NTFS{f' (libellé : {lbl!r})' if lbl else ''}…")
            cmd = ["mkfs.ntfs", "-f", partition]
            if lbl:
                cmd += ["-L", lbl]   # mkfs.ntfs supporte -L nativement
            run_command(cmd)
            label_applied_via_mkfs = bool(lbl)

        elif fs_choice == "ext4":
            logging.info(f"Formatage {partition} en EXT4{f' (libellé : {lbl!r})' if lbl else ''}…")
            cmd = ["mkfs.ext4", "-F", partition]
            if lbl:
                cmd += ["-L", lbl]   # mkfs.ext4 supporte -L nativement
            run_command(cmd)
            label_applied_via_mkfs = bool(lbl)

        elif fs_choice == "vfat":
            logging.info(f"Formatage {partition} en VFAT{f' (libellé : {lbl!r})' if lbl else ''}…")
            cmd = ["mkfs.vfat", "-F", "32", partition]
            if lbl:
                cmd += ["-n", lbl]   # mkfs.vfat supporte -n nativement
            run_command(cmd)
            label_applied_via_mkfs = bool(lbl)

        else:
            logging.error(f"Système de fichiers non supporté : {fs_choice}")
            sys.exit(1)

        logging.info(f"Partition {partition} formatée avec succès.")

        # Fallback : si le label n'a pas été intégré au mkfs pour une raison quelconque
        if lbl and not label_applied_via_mkfs:
            apply_disk_label(partition, fs_choice, lbl)

    except FileNotFoundError:
        logging.error(f"Utilitaire de formatage introuvable pour {fs_choice}. Assurez-vous que les outils nécessaires sont installés.")
        sys.exit(2)
    except CalledProcessError as e:
        logging.error(f"Échec du formatage de {partition} : {e}")
        sys.exit(1)