import logging
from utils import run_command
import sys
import time
from subprocess import CalledProcessError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_partition_name(disk_name: str) -> str:
    """
    Retourne le nom de la première partition pour un disque donné.
    Gère NVMe (nvme0n1 -> nvme0n1p1) et disques standards (sda -> sda1).
    """
    disk_name = disk_name.replace('/dev/', '')
    if 'nvme' in disk_name:
        return f"{disk_name}p1"
    else:
        return f"{disk_name}1"


def partition_disk(disk: str, partition_table: str = "mbr") -> None:
    """
    Partitionne le disque avec la table de partitions choisie.
    partition_table : "mbr" (msdos) ou "gpt". Défaut : "mbr".
    Gère correctement les disques NVMe et standards.
    """
    table = "msdos" if partition_table.lower() == "mbr" else "gpt"
    disk_name = disk.replace('/dev/', '')
    print(f"Partitionnement de {disk_name} avec table {partition_table.upper()}...")

    try:
        # Création de la table de partitions
        run_command(["parted", f"/dev/{disk_name}", "--script", "mklabel", table])

        # Partition primaire occupant 100% du disque
        run_command(["parted", f"/dev/{disk_name}", "--script", "mkpart", "primary", "0%", "100%"])

        # Informer le noyau
        run_command(["partprobe", f"/dev/{disk_name}"])

        time.sleep(2)

        print(f"Disque {disk_name} partitionné avec succès ({partition_table.upper()}).")

    except FileNotFoundError:
        logging.error("Erreur : commande `parted` introuvable.")
        sys.exit(2)
    except CalledProcessError as e:
        logging.error(f"Erreur : échec du partitionnement de {disk} : {e}")
        sys.exit(1)